# Build context: repo root (ctiq/)
# docker build -f apps/api-core/Dockerfile -t ctiq-api-core .

ARG NODE_VERSION=22

# ─────────────────────────────────────────────────────────────────────────────
# Base — pnpm via corepack + OpenSSL (required by Prisma query engine)
# ─────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN apt-get update -y && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@11.1.1 --activate

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 – prune: extract only the packages api-core depends on
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS pruner
WORKDIR /repo
COPY . .
RUN pnpm dlx turbo prune api-core --docker

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 – installer: install all deps
#
# Shared package source is included alongside json stubs because
# @repo/graphql-types and @repo/zod-validations run `postinstall: tsup`
# which requires their src/ to be present.
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS installer
WORKDIR /repo
COPY --from=pruner /repo/out/pnpm-lock.yaml ./pnpm-lock.yaml
COPY --from=pruner /repo/out/json/ .
COPY --from=pruner /repo/out/full/packages ./packages
RUN pnpm install --frozen-lockfile

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 – builder: compile everything
# Build order: db:generate → build:package (shared) → nest build (api-core)
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /repo
# prisma generate reads prisma.config.ts which resolves DATABASE_URL at load time.
# Placeholder is enough — generate only reads the schema, never connects.
# Also satisfies turbo.json globalEnv: ["DATABASE_URL"].
ARG DATABASE_URL=postgresql://placeholder:placeholder@localhost:5432/placeholder
ENV DATABASE_URL=${DATABASE_URL}
COPY --from=installer /repo/ .
COPY --from=pruner /repo/out/full/ .
RUN pnpm turbo build:package
RUN pnpm turbo build --filter=api-core

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 – runtime: slim production image
#
# pnpm's virtual store (.pnpm/) uses hard links to the content-addressable
# store. Docker COPY converts hard links to independent file copies, so
# node_modules is self-contained in the runtime image without the store.
#
# Workspace symlinks (node_modules/@repo/db → ../../packages/db) resolve
# to /app/packages/db, so we mirror the packages/ structure alongside dist/.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-slim AS runtime

ENV NODE_ENV=production \
    PORT=3001

RUN apt-get update -y && apt-get install -y --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

WORKDIR /app

# Root pnpm virtual store — all package files live under .pnpm/ here.
# pnpm uses relative symlinks, so the directory layout must mirror the builder:
#   /app/node_modules/                    ← this (the .pnpm store)
#   /app/apps/api-core/node_modules/      ← app-level symlinks into the store
#   /app/packages/*/                      ← workspace packages (@repo/*)
COPY --from=builder /repo/node_modules ./node_modules

# api-core's own node_modules.
# These are relative symlinks: @nestjs/core → ../../../node_modules/.pnpm/…
# which resolves to /app/node_modules/.pnpm/… in this image.
COPY --from=builder /repo/apps/api-core/node_modules ./apps/api-core/node_modules

# Workspace package manifests + built outputs + their own node_modules.
# Symlinks @repo/* → ../../../packages/* resolve to /app/packages/*.
# Each workspace package needs its own node_modules/ so that its runtime
# dependencies (e.g. @prisma/client for db, zod for zod-validations, peer
# deps for graphql-types) are reachable via normal Node module resolution.
# The symlinks inside those node_modules/ point to ../../node_modules/.pnpm/…
# which resolves to /app/node_modules/.pnpm/… — already present above.
COPY --from=builder /repo/packages/db/package.json              ./packages/db/
COPY --from=builder /repo/packages/db/dist                      ./packages/db/dist
COPY --from=builder /repo/packages/db/node_modules              ./packages/db/node_modules
COPY --from=builder /repo/packages/graphql-types/package.json   ./packages/graphql-types/
COPY --from=builder /repo/packages/graphql-types/dist           ./packages/graphql-types/dist
COPY --from=builder /repo/packages/graphql-types/node_modules   ./packages/graphql-types/node_modules
COPY --from=builder /repo/packages/zod-validations/package.json ./packages/zod-validations/
COPY --from=builder /repo/packages/zod-validations/dist         ./packages/zod-validations/dist
COPY --from=builder /repo/packages/zod-validations/node_modules ./packages/zod-validations/node_modules

# Compiled NestJS application (mirrored under apps/api-core/ to match symlink paths)
COPY --from=builder /repo/apps/api-core/dist ./apps/api-core/dist

RUN chown -R app:app /app
USER app

# WORKDIR must match the app's position so Node's module resolution walks up
# through /app/apps/api-core/node_modules → /app/node_modules correctly.
WORKDIR /app/apps/api-core

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get({host:'localhost',port:3001,path:'/'}, r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "dist/main"]

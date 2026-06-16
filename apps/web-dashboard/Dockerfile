# Build context: repo root (ctiq/)
# docker build -f apps/web-dashboard/Dockerfile -t ctiq-web-dashboard .

ARG NODE_VERSION=22

# ─────────────────────────────────────────────────────────────────────────────
# Base — pnpm via corepack
# ─────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-slim AS base
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@11.1.1 --activate

# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 – prune: extract only the packages web-dashboard depends on
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS pruner
WORKDIR /repo
COPY . .
RUN pnpm dlx turbo prune web-dashboard --docker

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 – installer: install all deps
#
# @repo/graphql-types has postinstall:tsup so its dist is built here.
# @repo/ui is source-only — no build step needed.
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS installer
WORKDIR /repo
COPY --from=pruner /repo/out/pnpm-lock.yaml ./pnpm-lock.yaml
COPY --from=pruner /repo/out/json/ .
COPY --from=pruner /repo/out/full/packages ./packages
RUN pnpm install --frozen-lockfile

# ─────────────────────────────────────────────────────────────────────────────
# Stage 3 – builder: compile everything
#
# Build order:
#   1. build:package  → tsup dist for @repo/db, @repo/graphql-types
#   2. turbo build    → runs generate:codegen (graphql-codegen + tsup) for
#                       @repo/generated-schemas-web, then `next build`
#
# NEXT_PUBLIC_* vars are inlined into JS bundles at build time.
# Pass every NEXT_PUBLIC_* your app uses via --build-arg at `docker build` time.
# ─────────────────────────────────────────────────────────────────────────────
FROM base AS builder
WORKDIR /repo

ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY --from=installer /repo/ .
COPY --from=pruner /repo/out/full/ .

# @repo/generated-schemas-web codegen reads apps/api-core/schema.gql.
# api-core is not in web-dashboard's dependency graph so turbo prune doesn't
# include it in out/full/ — copy the schema directly from the full repo copy
# that exists in the pruner stage.
COPY --from=pruner /repo/apps/api-core/schema.gql ./apps/api-core/schema.gql

# Build workspace packages that have a build:package script (@repo/db, etc.)
RUN pnpm turbo build:package

# Run the full build chain for web-dashboard:
#   - generate:codegen for @repo/generated-schemas-web (graphql-codegen + tsup)
#   - build for @repo/zod-validations
#   - next build for web-dashboard
RUN pnpm turbo build --filter=web-dashboard

# ─────────────────────────────────────────────────────────────────────────────
# Stage 4 – runtime: Next.js standalone output
#
# `output: standalone` in next.config.ts produces a self-contained server at
# .next/standalone/ that includes all necessary node_modules — no separate
# node_modules copy needed.
#
# Because outputFileTracingRoot is set to the repo root, the standalone
# directory mirrors the full monorepo layout:
#   .next/standalone/
#     apps/web-dashboard/
#       server.js          ← entry point
#       .next/             ← server-side assets
#     packages/            ← workspace package files traced by Next.js
#     node_modules/        ← production deps
#
# Static client assets (.next/static/) and public/ are NOT included in
# standalone and must be copied separately.
# ─────────────────────────────────────────────────────────────────────────────
FROM node:${NODE_VERSION}-slim AS runtime

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

RUN addgroup --system app && adduser --system --ingroup app --no-create-home app

# WORKDIR = repo root equivalent so relative paths in server.js resolve correctly
WORKDIR /app

COPY --from=builder /repo/apps/web-dashboard/.next/standalone            ./
COPY --from=builder /repo/apps/web-dashboard/.next/static                ./apps/web-dashboard/.next/static
COPY --from=builder /repo/apps/web-dashboard/public                      ./apps/web-dashboard/public

RUN chown -R app:app /app
USER app

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD node -e "require('http').get({host:'localhost',port:3000,path:'/'}, r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

# server.js lives at apps/web-dashboard/server.js inside the standalone tree
CMD ["node", "apps/web-dashboard/server.js"]

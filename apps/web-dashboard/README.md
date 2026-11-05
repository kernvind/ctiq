# web-dashboard

Next.js 16 (App Router) frontend for ctiq. It talks only to **api-core** over GraphQL; it never
reaches inference-service or the database directly.

## Surfaces

- **Public (no account)** — `app/(public)/`: home + semantic search (`/search`, URL-driven via `?q=`),
  trial detail (`/search/[nctId]`), side-by-side compare (`/compare?ids=…`), `/login`, `/signup`.
- **Authed** — `app/dashboard/`: role-aware home, trials, saved trials (`/dashboard/saved`),
  saved landscapes with "new since last check" (`/dashboard/landscapes`), eligibility match
  (`/dashboard/match`) and portfolio screening (`/dashboard/screen`).

## Develop

From the repo root:

```bash
pnpm install
pnpm turbo run generate:codegen        # typed GraphQL SDK; re-run when the GraphQL schema changes
pnpm --filter web-dashboard dev        # http://localhost:3000
```

Needs api-core running (default `http://localhost:3001`); copy `.env.example` to `.env` first.
See the root [README](../../README.md) for the full local stack.

## Scripts

| Command | Purpose |
|---|---|
| `pnpm --filter web-dashboard dev` | dev server |
| `pnpm --filter web-dashboard build` / `start` | production build / serve |
| `pnpm --filter web-dashboard test` | Vitest unit tests |
| `pnpm --filter web-dashboard lint` | ESLint |
| `pnpm --filter web-dashboard codegen` | GraphQL Code Generator |

## Structure

- `app/` — routes and layouts (Server Components by default; add `"use client"` only where needed)
- `features/`, `components/`, `hooks/`, `lib/` — feature code, shared UI, hooks, server actions and utilities
- `proxy.ts` — request-time auth/route protection
- UI primitives come from `@repo/ui` (shadcn); GraphQL types and the SDK from `@repo/graphql-types`
  and `@repo/generated-schemas-web`.

## Configuration

`BACKEND_URL` (server-side), `NEXT_PUBLIC_API_URL` (browser, baked at build time) and
`COOKIE_SECURE`. See `.env.example`.

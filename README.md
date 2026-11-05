# ctiq — Clinical Trial Intelligence Platform

Semantic search and analysis over public [ClinicalTrials.gov](https://clinicaltrials.gov) data,
for patients, clinicians, competitive-intelligence analysts and internal admins. Trials are
embedded locally and searched with pgvector; an optional LLM planner turns natural-language
queries into structured filters.

> **What's built vs. planned:** see [`docs/STATUS.md`](docs/STATUS.md) (shipped features,
> in-flight work) and [`docs/ROADMAP.md`](docs/ROADMAP.md) (direction and priorities).

**No PHI is stored.** All trial data is public. Patient profiles used for eligibility matching
are never persisted. Never log raw search text or profiles — log lengths, counts and ids.

## Architecture

```
web-dashboard (Next.js, :3000)
      │  GraphQL
      ▼
api-core (NestJS + Apollo + Prisma, :3001)   ← only auth boundary: users, JWT, roles, saved data
      │  HTTP + X-Internal-Token
      ▼
inference-service (FastAPI, :8000)           ← planner → embed → pgvector search → trial cards
      │
      ▼
Postgres + pgvector  (schema `app` = Prisma/user data, schema `trials` = SQLAlchemy/trial data)
      ▲
pipelines/ctiq_etl (Prefect)  ← ClinicalTrials.gov API → Postgres (+ BigQuery / GCS)
```

| Path | What it is |
|---|---|
| `apps/web-dashboard` | Next.js 16 App Router UI. Public pages (search, trial detail, compare, login/signup) and the authed `/dashboard` (saved trials, landscapes, eligibility match, portfolio screening). Talks only to api-core. |
| `apps/api-core` | NestJS 11 (Fastify) GraphQL API. Auth, roles, user-state, orchestration. Calls inference-service for search and matching. Logs with `nestjs-pino`. |
| `ai-service/inference-service` | FastAPI service. Query planning (LLM with rule-based fallback), local `sentence-transformers` embeddings, pgvector search, eligibility evaluation. JSON logs and Prometheus `/metrics`. |
| `pipelines/ctiq_etl` | Prefect flows that ingest ClinicalTrials.gov, embed trials and load them. |
| `py-packages/ctiq-db` | SQLAlchemy 2 models + Alembic migrations for the **trial domain** (`trials` schema). Shared by inference-service and the ETL. |
| `packages/db` | Prisma 7 schema/client for the **user domain** (`app` schema). |
| `packages/*` | Shared TS packages: `graphql-types`, `zod-validations`, `generated-schemas-web` (GraphQL codegen), `ui` (shadcn components), `eslint-config`, `typescript-config`. |
| `infra/` | `hetzner/` (current production runbook), `monitoring/` (Prometheus/Loki/Grafana configs), `k8s/` + `terraform/` + `README.md` (GKE path, deferred). |
| `docs/` | `STATUS.md` and `ROADMAP.md`. |

**Domain boundary:** the two ORMs own *disjoint* tables in separate Postgres schemas. api-core
must not touch trial tables; the Python services must not touch user tables. Cross-domain links go
by id (for example a saved trial stores an NCT id), never a cross-ORM foreign key.

## Prerequisites

- Node **22** (`.nvmrc`) and **pnpm 11** (`corepack enable`)
- Python **3.12** and [Poetry](https://python-poetry.org)
- Docker (Testcontainers suites, per-service compose files)
- A Postgres with the **pgvector** extension

## Configuration

Each service reads its own gitignored `.env`. Variable names (set your own values):

| Service | Variables |
|---|---|
| `apps/api-core` | `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRES_IN`, `SEARCH_API_URL`, `SEARCH_API_TOKEN`, `FAST_API_VERSION_V1`, `FAST_API_SEARCH_TRIAL_PATH`, `FAST_API_MATCH_PATH`, `FAST_API_MATCH_PORTFOLIO_PATH` |
| `ai-service/inference-service` | `PG_DATABASE_URL`, `SEARCH_API_TOKEN`, `OPENAI_API_KEY` (optional — without it the rule-based planner is used), `LLM_MODEL`, `LOG_LEVEL`, `LOG_FORMAT` (`json` default, `text` for local reading), `HF_TOKEN` (Docker build) |
| `apps/web-dashboard` | `BACKEND_URL`, `NEXT_PUBLIC_API_URL`, `COOKIE_SECURE` |
| `pipelines/ctiq_etl` | see `pipelines/.env.example` |

`SEARCH_API_TOKEN` must be identical in api-core and inference-service.

> **Use a development database.** Point local `.env` files at a local or dev Postgres, never at the
> production Supabase project. `make migrate-all`, the ETL (`--full-load` truncates staging
> tables) and ordinary signup/login testing all write to whatever database the URL names.

## Run locally

```bash
make install                      # pnpm install + poetry install (inference, ETL)

# 1. Schema (Prisma → `app`, Alembic → `trials`); use a direct connection (port 5432), not a pooler
make migrate-all DATABASE_URL="postgresql://USER:PASS@HOST:5432/DB"

# 2. Trial data + embeddings (needed for search to return anything)
#    The ETL also writes to BigQuery/GCS — see pipelines/.env.example for the GCP settings.
cd pipelines/ctiq_etl && poetry run python -m src.flows.clinical_trials_flow    # add --full-load to reload

# 3. Services (separate terminals)
cd ai-service/inference-service && poetry run start_dev     # :8000
pnpm --filter api-core dev                                  # :3001
pnpm turbo run generate:codegen                             # once, and whenever the GraphQL schema changes
pnpm --filter web-dashboard dev                             # :3000
```

The first inference start loads the embedding model (slow); it warms up before serving.
Health check: `GET :8000/`. Metrics: `GET :8000/metrics`.

**Docker instead of native:** `make up-inference`, `make up-api`, `make up-web` (and the matching
`down-*` / `logs-*`) use the per-service compose files. They join an external `postgres_db`
Docker network that you must create by running a Postgres container on it first, and note that
`apps/api-core/docker-compose.yml` sets its own `DATABASE_URL`, overriding `.env`.

## Test

```bash
make test               # fast, no Docker: Turbo (JS/TS) + inference pytest + ETL pytest
make test-integration   # Docker required: api-core SQL + GraphQL e2e + inference pgvector (Testcontainers)
make test-all
```

CI (`.github/workflows/ci.yml`) runs the same three groups: JS/TS, Python, integration.

## Code generation

| When | Command |
|---|---|
| GraphQL schema or operations changed | `pnpm turbo run generate:codegen` (writes `apps/api-core/schema.gql`, regenerates the typed web SDK) |
| Prisma schema changed | `pnpm --filter @repo/db db:generate` (and `db:migrate` in dev) |
| Inference API changed | `make gen-api-types` (regenerates api-core's typed inference client from OpenAPI) |
| Trial-domain schema changed | add an Alembic migration in `py-packages/ctiq-db`, then `make migrate-alembic` |

## Observability

- **Logs:** inference-service writes one JSON object per line to stdout (`severity`, `message`,
  `request_id`, …); api-core logs through pino. Containers log to stdout only.
- **Metrics:** Prometheus at `inference-service:8000/metrics` — HTTP rate/latency/errors, embedding
  and vector-search latency, planner cache and routing, LLM latency and token usage.
- **Stack:** Prometheus + Loki + Alloy + Grafana, opt-in with `--profile monitoring` in
  `docker-compose.hetzner.yml`. See [`infra/hetzner/README.md`](infra/hetzner/README.md).

## Deployment

| Tier | Where | Docs |
|---|---|---|
| **Current** | One Hetzner VM, Docker Compose, Caddy for TLS (`docker-compose.hetzner.yml`, `Caddyfile`) | [`infra/hetzner/README.md`](infra/hetzner/README.md) |
| Later | GKE Autopilot via Terraform + Kustomize | [`infra/README.md`](infra/README.md) |

Postgres is Supabase (external). Production images are `linux/amd64` only.

.PHONY: schema-generate \
        docker-web-dashboard docker-api-core docker-inference docker-etl docker-all \
        up-api down-api logs-api \
        up-web down-web logs-web \
        up-inference down-inference logs-inference \
        tf-plan-shared tf-apply-shared \
        migrate-prisma migrate-alembic migrate-all

# ── Database migrations ────────────────────────────────────────────────────────
# Both tools read DATABASE_URL from the environment. Use the Supabase DIRECT
# connection (port 5432 / session mode) here — NOT the transaction pooler (6543),
# which breaks DDL and Prisma's migration engine.
#
# Always `prisma migrate deploy` (forward-only). Never `migrate dev` in shared
# environments — it diffs the whole schema and would clobber Alembic's tables.
#
# Usage:
#   make migrate-all DATABASE_URL="postgresql://...@db.<ref>.supabase.co:5432/postgres"

migrate-prisma:
	pnpm --filter @repo/db db:deploy

migrate-alembic:
	cd py-packages/ctiq-db && .venv/bin/alembic upgrade head

migrate-all: migrate-prisma migrate-alembic

# ── Terraform ─────────────────────────────────────────────────────────────────

tf-plan-shared:
	cd infra/terraform/shared && terraform plan -out=tfplan

tf-apply-shared:
	cd infra/terraform/shared && terraform apply tfplan

# ── Schema ─────────────────────────────────────────────────────────────────────

schema-generate:
	pnpm turbo schema:generate --filter=api-core

# ── Docker image builds ────────────────────────────────────────────────────────

# web-dashboard depends on schema-generate because the Dockerfile copies
# apps/api-core/schema.gql as a static file at build time.
docker-web-dashboard: schema-generate
	docker build -f apps/web-dashboard/Dockerfile -t ctiq-web-dashboard .

docker-api-core:
	docker build -f apps/api-core/Dockerfile -t ctiq-api-core .

docker-inference:
	docker build \
	  --secret id=hf_token,env=HF_TOKEN \
	  -f ai-service/inference-service/Dockerfile \
	  -t ctiq-inference .

docker-etl:
	docker build \
	  --secret id=hf_token,env=HF_TOKEN \
	  -f pipelines/ctiq_etl/Dockerfile \
	  -t ctiq-etl .

docker-all: docker-web-dashboard docker-api-core docker-inference docker-etl

# ── Local docker-compose ───────────────────────────────────────────────────────

up-api:
	docker compose -f apps/api-core/docker-compose.yml up --build -d

down-api:
	docker compose -f apps/api-core/docker-compose.yml down

logs-api:
	docker compose -f apps/api-core/docker-compose.yml logs -f

# --build inside compose triggers a Docker build, so schema-generate must run first.
up-web: schema-generate
	docker compose -f apps/web-dashboard/docker-compose.yml up --build -d

down-web:
	docker compose -f apps/web-dashboard/docker-compose.yml down

logs-web:
	docker compose -f apps/web-dashboard/docker-compose.yml logs -f

up-inference:
	docker compose -f ai-service/inference-service/docker-compose.yml up --build -d

down-inference:
	docker compose -f ai-service/inference-service/docker-compose.yml down

logs-inference:
	docker compose -f ai-service/inference-service/docker-compose.yml logs -f

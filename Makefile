.PHONY: schema-generate \
        docker-web-dashboard docker-api-core docker-inference docker-etl docker-all \
        up-api down-api logs-api \
        up-web down-web logs-web \
        up-inference down-inference logs-inference \
        tf-plan-shared tf-apply-shared \
        migrate-prisma migrate-alembic migrate-all \
        docker-auth push-api-core push-inference push-web-dashboard push-dev

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
	cd py-packages/ctiq-db && poetry install && .venv/bin/alembic upgrade head

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

# ── Build + push to Artifact Registry ──────────────────────────────────────────
# Mirrors what CI does. Override TAG with the git SHA for real deploys:
#   make push-dev TAG=$(git rev-parse --short HEAD)
#
# PLATFORM is pinned to linux/amd64 because GKE Autopilot nodes are amd64 and
# this is built on an arm64 Mac — without it, pods crash with "exec format
# error". Emulated amd64 builds are slower (the inference image especially);
# CI runs on native amd64 and is the fast path.

REGISTRY ?= us-central1-docker.pkg.dev/data-eng-470620/ctiq
TAG      ?= latest
PLATFORM ?= linux/amd64

# web-dashboard bakes NEXT_PUBLIC_API_URL into the JS bundle at build time.
# Override with the external api-core URL once an Ingress exists.
NEXT_PUBLIC_API_URL ?= http://localhost:3001/graphql

# One-time: let Docker authenticate to Artifact Registry via gcloud.
docker-auth:
	gcloud auth configure-docker us-central1-docker.pkg.dev

push-api-core:
	docker build --platform $(PLATFORM) \
	  -f apps/api-core/Dockerfile \
	  -t $(REGISTRY)/api-core:$(TAG) .
	docker push $(REGISTRY)/api-core:$(TAG)

push-inference:
	docker build --platform $(PLATFORM) \
	  --secret id=hf_token,env=HF_TOKEN \
	  -f ai-service/inference-service/Dockerfile \
	  -t $(REGISTRY)/inference-service:$(TAG) .
	docker push $(REGISTRY)/inference-service:$(TAG)

push-web-dashboard: schema-generate
	docker build --platform $(PLATFORM) \
	  --build-arg NEXT_PUBLIC_API_URL=$(NEXT_PUBLIC_API_URL) \
	  -f apps/web-dashboard/Dockerfile \
	  -t $(REGISTRY)/web-dashboard:$(TAG) .
	docker push $(REGISTRY)/web-dashboard:$(TAG)

push-dev: push-api-core push-inference push-web-dashboard

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

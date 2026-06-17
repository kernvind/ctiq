# ctiq Infrastructure & Deployment Runbook

End-to-end setup for deploying the ctiq platform to Google Kubernetes Engine
(GKE Autopilot) on GCP, with Terraform-managed infrastructure and Kustomize K8s
manifests.

## Stack at a glance

| Layer | Choice |
|---|---|
| Orchestration | GKE Autopilot (`ctiq-dev`, region `us-central1`) |
| IaC | Terraform, GCS remote backend |
| Image registry | Artifact Registry (`ctiq` repo) |
| Database | Supabase (managed Postgres, external) |
| Data warehouse | BigQuery (`healthcare_ai` dataset) |
| Auth to GCP | Workload Identity (pods) + Workload Identity Federation (CI) |
| Manifests | Kustomize (`base` + `overlays/dev`) |

### Constants used throughout

```
GCP project    : data-eng-470620
Region         : us-central1
GitHub repo    : kernvind/ctiq
State bucket    : ctiq-terraform-state-data-eng-470620
Registry        : us-central1-docker.pkg.dev/data-eng-470620/ctiq
GKE cluster    : ctiq-dev
K8s namespace  : dev
```

### Services deployed

| Service | Source | Port | Exposure |
|---|---|---|---|
| `api-core` (NestJS) | `apps/api-core` | 3001 | ClusterIP |
| `web-dashboard` (Next.js) | `apps/web-dashboard` | 3000 | ClusterIP |
| `inference-service` (FastAPI) | `ai-service/inference-service` | 8000 | ClusterIP (internal only) |

> `pipelines/ctiq_etl` is **not** deployed to GKE (intentionally excluded).

---

## 1. One-time local tooling

```bash
# Google Cloud SDK (Homebrew)
brew install --cask google-cloud-sdk

# GKE auth plugin — kubectl needs this to talk to the cluster
gcloud components install gke-gcloud-auth-plugin
# (if installed via Homebrew cask, the plugin ships with google-cloud-sdk)

# Verify the rest
kubectl version --client      # v1.34+, Kustomize bundled
terraform version             # 1.5+
docker version                # buildx required for --secret/--platform
```

---

## 2. gcloud authentication

Two **separate** credential stores — you need both:

```bash
# 1. User login (for gcloud CLI commands)
gcloud auth login

# 2. Application Default Credentials (for Terraform / client libraries)
gcloud auth application-default login
gcloud auth application-default set-quota-project data-eng-470620

# Point the CLI at the project
gcloud config set project data-eng-470620
```

> Skipping ADC causes Terraform to fail with `AUTH_PERMISSION_DENIED`.

---

## 3. Terraform — shared bootstrap (run once)

Creates the state bucket, Artifact Registry, enables APIs, and imports the
existing BigQuery dataset. State for this module lives **locally** (it
bootstraps the bucket every other module uses).

```bash
cd infra/terraform/shared
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Creates:
- GCS bucket `ctiq-terraform-state-data-eng-470620` (versioned)
- Artifact Registry repo `ctiq` (Docker)
- Enabled APIs: container, artifactregistry, storage, iam, iamcredentials,
  secretmanager, bigquery, compute, **cloudresourcemanager**
- BigQuery dataset `healthcare_ai` (imported, US multi-region)

Makefile shortcuts: `make tf-plan-shared`, `make tf-apply-shared`.

> **Note:** `cloudresourcemanager.googleapis.com` is required for project-level
> IAM bindings — without it the dev apply fails on the IAM module.

---

## 4. Terraform — dev environment

Provisions the GKE cluster, VPC, service accounts, and Workload Identity.

```bash
cd infra/terraform/envs/dev
terraform init      # configures the GCS backend (prefix envs/dev)
terraform plan -out=tfplan
terraform apply tfplan
```

Creates (16 resources):
- VPC `ctiq-dev-vpc` + subnet with secondary ranges (VPC-native)
- GKE Autopilot cluster `ctiq-dev` (private nodes, public endpoint,
  Workload Identity, `deletion_protection = false`)
- Service accounts: `ctiq-api-core-dev`, `ctiq-inference-dev`,
  `ctiq-github-deploy`
- Workload Identity Federation pool + provider (locked to `kernvind/ctiq`)
- IAM role bindings (secretmanager, storage, bigquery, artifactregistry,
  container.developer) + KSA↔GSA Workload Identity bindings

Key outputs (save the WIF ones for GitHub Actions later):

```
cluster_name                      = ctiq-dev
github_workload_identity_provider = projects/706801034765/locations/global/workloadIdentityPools/github-actions-pool/providers/github-provider
github_deploy_sa_email            = ctiq-github-deploy@data-eng-470620.iam.gserviceaccount.com
api_core_sa_email                 = ctiq-api-core-dev@data-eng-470620.iam.gserviceaccount.com
inference_sa_email                = ctiq-inference-dev@data-eng-470620.iam.gserviceaccount.com
```

> The IAM module has `depends_on = [module.gke]` because Workload Identity
> bindings reference `PROJECT.svc.id.goog`, which only exists once the cluster
> is created.

---

## 5. Configure kubectl

```bash
gcloud container clusters get-credentials ctiq-dev \
  --region us-central1 --project data-eng-470620

kubectl config current-context        # gke_data-eng-470620_us-central1_ctiq-dev
kubectl get namespaces                # confirm connectivity
```

> Autopilot shows no nodes until pods are scheduled — that's expected.

---

## 6. Database migrations (clean Supabase bootstrap)

Two ORMs, **same** database, **disjoint** tables — they coexist safely:

| Tool | Path | Owns | Version table |
|---|---|---|---|
| Prisma | `packages/db` | `User`, `Post` (auth) | `_prisma_migrations` |
| Alembic | `py-packages/ctiq-db` | clinical-trials schema | `alembic_version` |

Rules:
- Use the Supabase **DIRECT connection (port 5432, session mode)** for
  migrations — NOT the transaction pooler (6543).
- Always forward-only: `prisma migrate deploy`, `alembic upgrade head`.
  **Never** `prisma migrate dev` in shared environments (it diffs the whole
  schema and would clobber Alembic's tables).

```bash
make migrate-all DATABASE_URL="postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres"
```

> `migrations/env.py` rewrites `postgresql://` → `postgresql+psycopg://` so the
> same URL works for both Prisma and the psycopg3-based Alembic setup.

---

## 7. Kubernetes secrets (manual, never committed)

Runtime DB connections use the **pooler (port 6543)**. api-core (Prisma) needs
`?pgbouncer=true`; inference (asyncpg) can't parse that param — hence two keys.

```bash
kubectl create secret generic supabase-db -n dev \
  --from-literal=DATABASE_URL="postgresql://postgres:<pwd>@<ref>.pooler.supabase.com:6543/postgres?pgbouncer=true" \
  --from-literal=PG_DATABASE_URL="postgresql://postgres:<pwd>@<ref>.pooler.supabase.com:6543/postgres"

kubectl create secret generic api-core-secrets -n dev \
  --from-literal=JWT_SECRET="change-me-in-production" \
  --from-literal=SEARCH_API_TOKEN="test-token"
```

| Secret | Key | Consumed by |
|---|---|---|
| `supabase-db` | `DATABASE_URL` | api-core (Prisma, `?pgbouncer=true`) |
| `supabase-db` | `PG_DATABASE_URL` | inference (asyncpg, no param) |
| `api-core-secrets` | `JWT_SECRET` | api-core |
| `api-core-secrets` | `SEARCH_API_TOKEN` | api-core → inference auth |

---

## 8. Build & push images

```bash
make docker-auth         # one-time: configure-docker for Artifact Registry
make push-dev            # builds linux/amd64, pushes :latest

# Pin to a git SHA (what CI does):
make push-dev TAG=$(git rev-parse --short HEAD)
```

Pushes to `us-central1-docker.pkg.dev/data-eng-470620/ctiq/<service>`.

> **Platform:** builds are pinned to `linux/amd64` because Autopilot nodes are
> amd64. On an arm64 Mac this builds under emulation (slow for the inference
> image). CI runs native amd64 and is the fast path.

> **HF_TOKEN:** inference and ETL builds accept an optional BuildKit secret
> (`--secret id=hf_token,env=HF_TOKEN`). The model is public, so it's optional;
> the token never lands in an image layer.

---

## 9. Deploy

```bash
kubectl apply -k infra/k8s/overlays/dev
kubectl get pods -n dev -w
```

The dev overlay (`infra/k8s/overlays/dev`) layers onto `base`:
- All workloads run as **Spot Pods** (`nodeSelector` + toleration) for low cost
- KSA→GSA Workload Identity annotations (`ctiq-*-dev` service accounts)
- Images mapped to the Artifact Registry repo (CI sets `newTag` to git SHA)
- ConfigMaps for non-sensitive config (FastAPI paths, inter-service URLs,
  `COOKIE_SECURE=false` for HTTP dev)

In-cluster service wiring:
- api-core → inference via `SEARCH_API_URL=http://inference-service:8000`
- web-dashboard → api-core via `BACKEND_URL=http://api-core:3001`

> **BFF architecture — only web-dashboard needs external exposure.** All
> api-core calls happen in Next.js Server Actions (server-side) via
> `BACKEND_URL=http://api-core:3001`. The browser never calls api-core
> directly (`packages/generated-schemas-web` targets `BACKEND_URL`, not
> `NEXT_PUBLIC_API_URL`, and the SDK is only imported in `"use server"`
> files). So **api-core and inference stay `ClusterIP` (private)** — better
> security — and the future Ingress covers web-dashboard alone.

Validate the rendered manifests without applying:

```bash
kubectl kustomize infra/k8s/overlays/dev
```

---

## 10. Teardown (stop billing) & bring-up

The dev env is cheap to cycle down/up to avoid idle charges. The main costs are
the **Autopilot cluster management fee** (~$0.10/hr), **Cloud NAT** (~$0.044/hr),
and the running Spot pods. Scaling pods to zero does **not** stop the cluster
fee or NAT — a `terraform destroy` does.

### Teardown

```bash
cd infra/terraform/envs/dev
terraform plan -destroy -out=destroy.tfplan   # review: ~18 resources
terraform apply destroy.tfplan
rm -f destroy.tfplan
```

This destroys the **cluster, VPC, subnet, Cloud Router + NAT, service accounts,
and Workload Identity pool/bindings**. Because the IAM module has
`depends_on = [module.gke]`, a destroy targeting `module.gke` cascades to IAM
too — so it's an all-or-nothing teardown of the env (the IAM resources are free
anyway).

**What survives** (cents/month, and what makes bring-up fast):

| Survives | Where | Why it matters |
|---|---|---|
| Artifact Registry images | `shared/` | No image rebuild on return |
| Terraform state bucket | `shared/` | State intact |
| BigQuery `healthcare_ai` | `shared/` | Preserved |
| Supabase data | external | Loaded data is safe — no re-migration |

Verify everything is gone:

```bash
gcloud container clusters list --project data-eng-470620   # empty
gcloud compute routers list --project data-eng-470620      # empty
```

### Bring-up

```bash
cd infra/terraform/envs/dev
terraform apply                       # recreates cluster + NAT + IAM (~15 min)
```

> **Workload Identity pool soft-delete:** WI pools are soft-deleted for 30 days.
> If `terraform apply` errors recreating `github-actions-pool`, undelete it once
> and re-apply:
> ```bash
> gcloud iam workload-identity-pools undelete github-actions-pool --location=global
> ```

Then reconnect kubectl, recreate the secrets (values unchanged — see sections 5
and 7), and redeploy:

```bash
gcloud container clusters get-credentials ctiq-dev --region us-central1 --project data-eng-470620

kubectl create secret generic supabase-db -n dev \
  --from-literal=DATABASE_URL="postgresql://postgres.<ref>:<pwd>@<host>.pooler.supabase.com:6543/postgres?pgbouncer=true" \
  --from-literal=PG_DATABASE_URL="postgresql://postgres.<ref>:<pwd>@<host>.pooler.supabase.com:5432/postgres"
kubectl create secret generic api-core-secrets -n dev \
  --from-literal=JWT_SECRET="change-me-in-production" \
  --from-literal=SEARCH_API_TOKEN="test-token"

kubectl apply -k infra/k8s/overlays/dev
kubectl get pods -n dev -w
```

No re-migration needed — the schema and data live in Supabase. The
Artifact Registry images are still tagged `:latest`, so pods pull immediately.

> **Reminder:** inference uses the Supabase **session pooler (5432)** in
> `PG_DATABASE_URL`, not the transaction pooler (6543) — the latter breaks
> asyncpg prepared statements used by pgvector's `register_vector`.

---

## Repository layout

```
infra/
├── README.md                    # this file
├── .gitignore                   # excludes tfstate, tfvars, .terraform, tfplan
├── terraform/
│   ├── shared/                  # one-time bootstrap (local state)
│   ├── modules/
│   │   ├── gke/                 # VPC + Autopilot cluster
│   │   ├── gcs/                 # ETL bucket module (not wired into dev)
│   │   └── iam/                 # service accounts + Workload Identity (+ WIF)
│   └── envs/
│       └── dev/                 # dev root module (GCS backend)
└── k8s/
    ├── base/                    # env-agnostic manifests
    │   ├── api-core/
    │   ├── inference-service/
    │   └── web-dashboard/
    └── overlays/
        └── dev/                 # Spot, WI annotations, images, configmaps
```

---

## Common operations

```bash
# Roll a deployment after a secret/config change
kubectl rollout restart deployment/api-core -n dev

# Logs
kubectl logs -n dev deployment/api-core -f

# Describe a stuck pod
kubectl describe pod -n dev <pod>

# Update image tag and redeploy (manual)
cd infra/k8s/overlays/dev
kubectl kustomize . | kubectl apply -f -
```

---

## Security invariants

- **Never** commit `terraform.tfvars`, `*.tfstate`, `.terraform/`, or `tfplan`
  (enforced by `infra/.gitignore`).
- **Never** put secrets in Docker images — HF_TOKEN uses BuildKit secret mounts.
- **Never** use service-account JSON keys in pods — Workload Identity only.
- **Never** store GCP credentials as K8s Secrets or Docker env vars.
- DB credentials live only in K8s Secrets (created via `kubectl`, out of git).
- GitHub Actions WIF is restricted to the `kernvind/ctiq` repo via
  `attribute_condition`.

---

## Pending work

- [ ] GitHub Actions CI/CD (build-push + gated migrate + deploy via WIF)
- [ ] Ingress / external exposure for **web-dashboard only** (api-core +
      inference stay private — BFF architecture)
- [ ] Slim the inference image (~4.3 GB → ~2.8 GB) by installing CPU-only torch
- [ ] Real dependency-free `/health` in api-core (so liveness isn't TCP-only)
- [ ] External Secrets Operator — back the K8s secrets with GCP Secret Manager
- [ ] Drop the dead `NEXT_PUBLIC_API_URL` build-arg (unused — BFF)
- [ ] staging / prod environments (`deletion_protection = true`, non-Spot)

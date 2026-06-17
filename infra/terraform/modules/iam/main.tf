locals {
  # Workload Identity pool — all KSA → GSA bindings reference this
  wi_pool = "${var.project_id}.svc.id.goog"
}

# ── api-core ──────────────────────────────────────────────────────────────────
# Needs Secret Manager access (JWT secret, DB URL via ESO in future)
# and read access to GCS for any static assets.

resource "google_service_account" "api_core" {
  project      = var.project_id
  account_id   = "ctiq-api-core-${var.env}"
  display_name = "ctiq api-core (${var.env})"
}

resource "google_project_iam_member" "api_core_secret" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.api_core.email}"
}

# Binds the GCP SA to the Kubernetes SA used by the api-core pod
resource "google_service_account_iam_member" "api_core_wi" {
  service_account_id = google_service_account.api_core.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.wi_pool}[${var.env}/api-core-ksa]"
}

# ── inference-service ─────────────────────────────────────────────────────────
# Reads/writes GCS for any model artefacts.
# Reads BigQuery for trial data lookups.

resource "google_service_account" "inference" {
  project      = var.project_id
  account_id   = "ctiq-inference-${var.env}"
  display_name = "ctiq inference-service (${var.env})"
}

resource "google_project_iam_member" "inference_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.inference.email}"
}

resource "google_project_iam_member" "inference_bq" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.inference.email}"
}

resource "google_service_account_iam_member" "inference_wi" {
  service_account_id = google_service_account.inference.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${local.wi_pool}[${var.env}/inference-ksa]"
}

# ── web-dashboard ─────────────────────────────────────────────────────────────
# No GCP service account needed — Next.js standalone makes no direct GCP API
# calls. All data goes through api-core. Pod runs with the default KSA.

# ── GitHub Actions ────────────────────────────────────────────────────────────
# Workload Identity Federation lets GitHub Actions authenticate to GCP via OIDC
# — no service account key files downloaded or stored as GitHub secrets.

resource "google_service_account" "github_deploy" {
  project      = var.project_id
  account_id   = "ctiq-github-deploy"
  display_name = "GitHub Actions deploy"
}

resource "google_project_iam_member" "github_registry" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

resource "google_project_iam_member" "github_gke" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# OIDC pool — GitHub's token issuer is registered here
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Only tokens from your repo can exchange for GCP credentials
  attribute_condition = "assertion.repository == '${var.github_repo}'"
}

resource "google_service_account_iam_member" "github_wi" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repo}"
}

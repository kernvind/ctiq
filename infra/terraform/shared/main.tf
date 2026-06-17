terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  # No backend block here — this module bootstraps the GCS bucket that all
  # other modules use as their backend. State lives locally in this directory.
  # Run `terraform init && terraform apply` once, then never touch this again.
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable required GCP APIs ───────────────────────────────────────────────────
# These must be enabled before any other resource in any module can be created.
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",           # GKE
    "artifactregistry.googleapis.com",    # Artifact Registry
    "storage.googleapis.com",              # GCS
    "cloudresourcemanager.googleapis.com", # Project-level IAM bindings
    "iam.googleapis.com",                  # IAM
    "iamcredentials.googleapis.com",      # Workload Identity Federation
    "secretmanager.googleapis.com",       # Secret Manager
    "bigquery.googleapis.com",            # BigQuery (ETL)
    "compute.googleapis.com",             # VPC / networking
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ── Terraform state bucket ─────────────────────────────────────────────────────
# All env modules (dev/staging/prod) store their state here.
# Versioning keeps the last 10 state versions — safe rollback without hoarding.
resource "google_storage_bucket" "tf_state" {
  name                        = "ctiq-terraform-state-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition  { num_newer_versions = 10 }
    action     { type = "Delete" }
  }

  depends_on = [google_project_service.apis]
}

# ── Artifact Registry ──────────────────────────────────────────────────────────
# Single registry for all environments — images are distinguished by tag (git SHA).
resource "google_artifact_registry_repository" "ctiq" {
  repository_id = "ctiq"
  format        = "DOCKER"
  location      = var.region
  description   = "ctiq service images"

  depends_on = [google_project_service.apis]
}

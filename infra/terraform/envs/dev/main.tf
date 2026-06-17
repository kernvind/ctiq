terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

# ── GKE cluster ───────────────────────────────────────────────────────────────
# deletion_protection = false so the dev cluster can be torn down freely.
# Spot is NOT a cluster-level setting in Autopilot — it is applied per-pod
# in the K8s manifests via nodeSelector (cloud.google.com/gke-spot: "true").
# The dev Kustomize overlay will add Spot to all workloads.

module "gke" {
  source = "../../modules/gke"

  project_id          = var.project_id
  region              = var.region
  env                 = "dev"
  deletion_protection = false
}

# ── IAM + Workload Identity ───────────────────────────────────────────────────
# One GCP service account per service, bound to its Kubernetes service account.
# Pods authenticate to GCP APIs (GCS, BigQuery) without any credential files.

module "iam" {
  source = "../../modules/iam"

  project_id  = var.project_id
  env         = "dev"
  github_repo = var.github_repo
}


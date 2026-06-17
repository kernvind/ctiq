# ── VPC ───────────────────────────────────────────────────────────────────────
# Custom VPC so we control IP ranges — required for Autopilot VPC-native mode.

resource "google_compute_network" "ctiq" {
  name                    = "ctiq-${var.env}-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "ctiq" {
  name          = "ctiq-${var.env}-subnet"
  project       = var.project_id
  region        = var.region
  network       = google_compute_network.ctiq.id
  ip_cidr_range = "10.0.0.0/20"    # 4096 node IPs — more than enough

  # Secondary ranges are required for VPC-native GKE:
  # pods range must be large enough for max_pods_per_node × max_nodes
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.16.0.0/14"  # ~262k pod IPs
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.20.0.0/20"  # 4096 service IPs
  }
}

# ── GKE Autopilot cluster ──────────────────────────────────────────────────────
# Autopilot: Google manages node pools, OS patching, and scaling.
# You pay per pod CPU/memory request, not per node — scales to near-zero in dev.

resource "google_container_cluster" "ctiq" {
  name     = "ctiq-${var.env}"
  project  = var.project_id
  location = var.region

  enable_autopilot = true

  # Private nodes — no public IPs on worker nodes.
  # Public endpoint kept on so kubectl works from your laptop.
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # VPC-native networking — required for Autopilot
  networking_mode = "VPC_NATIVE"
  network         = google_compute_network.ctiq.name
  subnetwork      = google_compute_subnetwork.ctiq.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Workload Identity — pods authenticate to GCP APIs without any key files
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # REGULAR channel: GKE upgrades the cluster automatically, ~2 minor versions
  # behind latest. Balances stability with security patches.
  release_channel {
    channel = "REGULAR"
  }

  # Ship logs and metrics to Cloud Operations (formerly Stackdriver)
  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  deletion_protection = var.deletion_protection
}

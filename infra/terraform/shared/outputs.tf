output "state_bucket" {
  description = "GCS bucket name — paste this into backend.tf for each env module"
  value       = google_storage_bucket.tf_state.name
}

output "registry_url" {
  description = "Artifact Registry base URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/ctiq"
}

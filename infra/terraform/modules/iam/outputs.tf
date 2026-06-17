output "api_core_sa_email" {
  description = "api-core GCP service account email — annotate the K8s service account with this"
  value       = google_service_account.api_core.email
}

output "inference_sa_email" {
  description = "inference-service GCP service account email"
  value       = google_service_account.inference.email
}

output "github_workload_identity_provider" {
  description = "Paste this into GitHub Actions variable GCP_WORKLOAD_IDENTITY_PROVIDER"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "github_deploy_sa_email" {
  description = "Paste this into GitHub Actions variable GCP_DEPLOY_SA_EMAIL"
  value       = google_service_account.github_deploy.email
}

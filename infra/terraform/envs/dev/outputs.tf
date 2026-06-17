output "cluster_name" {
  description = "GKE cluster name"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "GKE control plane endpoint"
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "api_core_sa_email" {
  description = "GCP service account email for api-core pods"
  value       = module.iam.api_core_sa_email
}

output "inference_sa_email" {
  description = "GCP service account email for inference-service pods"
  value       = module.iam.inference_sa_email
}

output "github_workload_identity_provider" {
  description = "WIF provider resource name — paste into GitHub Actions workflow"
  value       = module.iam.github_workload_identity_provider
}

output "github_deploy_sa_email" {
  description = "Service account GitHub Actions impersonates to push images and deploy"
  value       = module.iam.github_deploy_sa_email
}

output "kubectl_credentials_command" {
  description = "Run this after terraform apply to configure kubectl"
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --region ${var.region} --project ${var.project_id}"
}

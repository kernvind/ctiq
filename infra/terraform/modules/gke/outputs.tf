output "cluster_name" {
  description = "GKE cluster name — used by GitHub Actions to get kubectl credentials"
  value       = google_container_cluster.ctiq.name
}

output "cluster_id" {
  description = "Full cluster resource ID — used by IAM module to bind Workload Identity"
  value       = google_container_cluster.ctiq.id
}

output "cluster_endpoint" {
  description = "Cluster API server endpoint"
  value       = google_container_cluster.ctiq.endpoint
  sensitive   = true
}

output "network_name" {
  description = "VPC network name — referenced by other modules if needed"
  value       = google_compute_network.ctiq.name
}

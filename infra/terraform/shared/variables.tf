variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "dataset_owner_email" {
  description = "Google account that owns the healthcare_ai BigQuery dataset (set in the gitignored terraform.tfvars)"
  type        = string
}

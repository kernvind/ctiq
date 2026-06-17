variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for the cluster"
  type        = string
}

variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "deletion_protection" {
  description = "Prevent accidental cluster deletion. Set false for dev, true for prod."
  type        = bool
  default     = true
}

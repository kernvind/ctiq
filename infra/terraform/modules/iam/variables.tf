variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in org/repo format (e.g. baljotsingh/ctiq)"
  type        = string
}

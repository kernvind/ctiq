variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region — should match the GKE cluster region"
  type        = string
}

variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "etl_retention_days" {
  description = "Days to keep ETL Parquet files before deleting them (they are loaded to BigQuery after each run)"
  type        = number
  default     = 30
}

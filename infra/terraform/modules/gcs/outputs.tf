output "etl_bucket_name" {
  description = "ETL staging bucket name — set as GCS_BUCKET env var in the ETL CronJob"
  value       = google_storage_bucket.etl.name
}

output "etl_bucket_url" {
  description = "ETL staging bucket URL (gs:// form)"
  value       = "gs://${google_storage_bucket.etl.name}"
}

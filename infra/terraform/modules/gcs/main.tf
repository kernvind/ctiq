# ── ETL staging bucket ────────────────────────────────────────────────────────
# The ETL pipeline writes Parquet files here, then loads them into BigQuery.
# Files are temporary — lifecycle rule deletes them after etl_retention_days
# so the bucket doesn't accumulate stale data indefinitely.
#
# Bucket name includes project_id for global uniqueness (GCS names are global).

resource "google_storage_bucket" "etl" {
  name                        = "ctiq-etl-${var.env}-${var.project_id}"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  lifecycle_rule {
    condition { age = var.etl_retention_days }
    action    { type = "Delete" }
  }
}

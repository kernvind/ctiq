# ── BigQuery dataset ──────────────────────────────────────────────────────────
# Kept in US multi-region (better than single-region, no downside to moving).
# The GCS bucket (bitziv_health_data) was empty so it is NOT imported here —
# a fresh bucket will be created in us-central1 alongside the GKE cluster.

resource "google_bigquery_dataset" "healthcare_ai" {
  dataset_id = "healthcare_ai"
  location   = "US"

  max_time_travel_hours = 168

  access {
    role          = "OWNER"
    user_by_email = "baljotsingh1986@gmail.com"
  }
  access {
    role          = "WRITER"
    special_group = "projectWriters"
  }
  access {
    role          = "OWNER"
    special_group = "projectOwners"
  }
  access {
    role          = "READER"
    special_group = "projectReaders"
  }
}

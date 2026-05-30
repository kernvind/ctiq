"""
Convert transformed clinical trials records into Parquet files and upload to
GCS in a Hive-partitioned layout that BigQuery can load directly.
 
Pipeline:
  transform_study()         (per study)
       │
       ▼
  list[dict]                (batched in memory)
       │
       ▼
  studies_to_arrow_tables() (one pa.Table per target)
       │
       ▼
  write_tables_to_gcs()     (Parquet upload, partitioned by ingestion_date)
 
GCS layout:
  gs://{bucket}/{prefix}/{table}/ingestion_date=YYYY-MM-DD/batch_{id}.parquet
 
  Example:
    gs://my-data-lake/clinical_trials/staging/trial/
        ingestion_date=2026-05-22/batch_a1b2c3d4e5f6.parquet
 
Each table directory follows Hive partitioning so BigQuery external tables
or LOAD jobs with `hive_partition_uri_prefix` pick up `ingestion_date`
automatically.
 
Required packages:
    pip install pyarrow google-cloud-storage
"""
from __future__ import annotations
 
import logging
from datetime import date, datetime
from typing import Iterable, Optional
from unicodedata import name
 
import pyarrow as pa
from src.schemas import tables
 
logger = logging.getLogger(__name__)
 
 
# ─── Reusable nested struct types ────────────────────────────────────────────
 
_CONTACT_STRUCT = pa.struct([
    pa.field("name", pa.string()),
    pa.field("role", pa.string()),
    pa.field("phone", pa.string()),
    pa.field("email", pa.string()),
])
 
_SECONDARY_ID_STRUCT = pa.struct([
    pa.field("id", pa.string()),
    pa.field("type", pa.string()),
    pa.field("link", pa.string()),
])
 
_COLLABORATOR_STRUCT = pa.struct([
    pa.field("name", pa.string()),
    pa.field("class", pa.string()),
])
 
_REFERENCE_STRUCT = pa.struct([
    pa.field("citation", pa.string()),
    pa.field("type", pa.string()),
    pa.field("pmid", pa.int64()),
])
 
 
# ─── Per-table PyArrow schemas (mirror BigQuery types) ───────────────────────
 
TRIAL_SCHEMA = pa.schema([
    # Identification
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("brief_title", pa.string()),
    pa.field("official_title", pa.string()),
    pa.field("acronym", pa.string()),
    pa.field("organization", pa.string()),
    pa.field("organization_class", pa.string()),
    pa.field("secondary_ids", pa.list_(_SECONDARY_ID_STRUCT)),
 
    # Status / Dates
    pa.field("overall_status", pa.string()),
    pa.field("has_results", pa.bool_()),
    pa.field("start_date", pa.date32()),
    pa.field("start_date_type", pa.string()),
    pa.field("completion_date", pa.date32()),
    pa.field("primary_completion_date", pa.date32()),
    pa.field("study_first_post_date", pa.date32()),
    pa.field("last_update_post_date", pa.date32()),
 
    # Sponsor
    pa.field("lead_sponsor_name", pa.string()),
    pa.field("lead_sponsor_class", pa.string()),
    pa.field("collaborators", pa.list_(_COLLABORATOR_STRUCT)),
    pa.field("responsible_party_investigator", pa.string()),
    pa.field("responsible_party_affiliation", pa.string()),
    pa.field("responsible_party_type", pa.string()),
 
    # Design
    pa.field("study_type", pa.string()),
    pa.field("phases", pa.list_(pa.string())),
    pa.field("allocation", pa.string()),
    pa.field("intervention_model", pa.string()),
    pa.field("primary_purpose", pa.string()),
    pa.field("masking", pa.string()),
    pa.field("enrollment_count", pa.int64()),
    pa.field("enrollment_type", pa.string()),
 
    # Conditions / Keywords
    pa.field("conditions", pa.list_(pa.string())),
    pa.field("keywords", pa.list_(pa.string())),
 
    # Eligibility
    pa.field("eligibility_criteria", pa.string()),
    pa.field("min_age_raw", pa.string()),
    pa.field("max_age_raw", pa.string()),
    pa.field("min_age_years", pa.float64()),
    pa.field("max_age_years", pa.float64()),
    pa.field("sex", pa.string()),
    pa.field("std_ages", pa.list_(pa.string())),
    pa.field("healthy_volunteers", pa.bool_()),
 
    # Description
    pa.field("brief_summary", pa.string()),
    pa.field("detailed_description", pa.string()),
 
    # Oversight / Regulatory
    pa.field("is_fda_regulated_drug", pa.bool_()),
    pa.field("is_fda_regulated_device", pa.bool_()),
    pa.field("has_dmc", pa.bool_()),
 
    # Contacts / references
    pa.field("central_contacts", pa.list_(_CONTACT_STRUCT)),
    pa.field("references", pa.list_(_REFERENCE_STRUCT)),
 
    # Lineage
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
])
 
LOCATION_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("facility", pa.string()),
    pa.field("city", pa.string()),
    pa.field("state", pa.string()),
    pa.field("country", pa.string()),
    pa.field("zip", pa.string()),
    pa.field("status", pa.string()),
    pa.field("latitude", pa.float64()),
    pa.field("longitude", pa.float64()),
    pa.field("contacts", pa.list_(_CONTACT_STRUCT)),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])
 
MESH_TERM_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("mesh_id", pa.string()),
    pa.field("mesh_term", pa.string()),
    pa.field("browse_type", pa.string()),
    pa.field("is_ancestor", pa.bool_()),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])
 
ARM_GROUP_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("label", pa.string()),
    pa.field("type", pa.string()),
    pa.field("description", pa.string()),
    pa.field("intervention_names", pa.list_(pa.string())),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])
 
INTERVENTION_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("type", pa.string()),
    pa.field("name", pa.string()),
    pa.field("description", pa.string()),
    pa.field("other_names", pa.list_(pa.string())),
    pa.field("arm_group_labels", pa.list_(pa.string())),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])
 
OUTCOME_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("outcome_type", pa.string()),     # 'primary' | 'secondary' | 'other'
    pa.field("measure", pa.string()),
    pa.field("description", pa.string()),
    pa.field("time_frame", pa.string()),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])
 
OFFICIAL_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("name", pa.string()),
    pa.field("affiliation", pa.string()),
    pa.field("role", pa.string()),
    pa.field("ingestion_date", pa.date32(), nullable=False),
    pa.field("last_update_post_date", pa.date32()),
])

EMBEDDING_SCHEMA = pa.schema([
    pa.field("nct_id", pa.string(), nullable=False),
    pa.field("field_type", pa.string(), nullable=False),
    pa.field("chunk_id", pa.int64(), nullable=False),
    pa.field("chunk_text", pa.string()),
    pa.field("source_hash", pa.string(), nullable=False),
    pa.field("embedding", pa.list_(pa.float64()), nullable=False),
    pa.field("model_version", pa.string(), nullable=False),
    pa.field("ingested_at", pa.timestamp("us", tz="UTC"), nullable=False),
])

TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "trial": TRIAL_SCHEMA,
    "locations": LOCATION_SCHEMA,
    "mesh_terms": MESH_TERM_SCHEMA,
    "arm_groups": ARM_GROUP_SCHEMA,
    "interventions": INTERVENTION_SCHEMA,
    "outcomes": OUTCOME_SCHEMA,
    "officials": OFFICIAL_SCHEMA,
}
 
# Child tables that are 1-to-many off `trial`
_CHILD_TABLES = ("locations", "mesh_terms", "arm_groups",
                "interventions", "outcomes", "officials")

# ─── Convert batched dicts -> PyArrow Tables ─────────────────────────────────
 
def _studies_to_arrow_tables(
    transformed_studies: Iterable[Optional[dict]],
    ingestion_date: date,
    ingested_at: datetime,
) -> dict[str, pa.Table]:
    """
    Convert a batch of `transform_study()` outputs into one `pa.Table`
    per target table. None entries (skipped studies) are filtered out.
 
    Adds `ingestion_date` to every row, plus `ingested_at` on `trial`.
    """
    buckets: dict[str, list[dict]] = {k: [] for k in TABLE_SCHEMAS}
 
    for study in transformed_studies:
        if not study:
            continue
 
        trial_row = dict(study["trial"])
        trial_row["ingestion_date"] = ingestion_date
        trial_row["ingested_at"] = ingested_at
        buckets["trial"].append(trial_row)
 
        for key in _CHILD_TABLES:
            for row in (study.get(key) or []):
                row = dict(row)
                row["ingestion_date"] = ingestion_date
                buckets[key].append(row)
 
    tables: dict[str, pa.Table] = {}
    for name, rows in buckets.items():
        schema = TABLE_SCHEMAS[name]
        # from_pylist + explicit schema correctly handles:
        #  - nested structs / lists
        #  - missing keys -> null
        #  - datetime.date -> date32, tz-aware datetime -> timestamp[us, UTC]
        tables[name] = pa.Table.from_pylist(rows, schema=schema)
    return tables

def _embeddings_to_arrow_tables(
    embeddings: list[dict],
) -> dict[str,pa.Table]:
    """
    Convert a batch of embedding dictionaries into a PyArrow Table.
    """
    tables: dict[str, pa.Table] = {}
    tables['embeddings'] = pa.Table.from_pylist(embeddings, schema=EMBEDDING_SCHEMA)
    return tables
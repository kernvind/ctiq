"""
Load task: ClinicalTrial records → month-partitioned Parquet on GCS → BigQuery.

GCS layout (Hive-style, one file per calendar month)
----------------------------------------------------
    gs://bitziv_health_data/clinical_trials_gov_stg/
    └── {run_id}/
        ├── year=2000/month=01/data.parquet
        ├── year=2000/month=02/data.parquet
        ...
        └── year=2024/month=12/data.parquet

Each run is isolated under its own {run_id} folder so concurrent or
replayed runs never overwrite each other.  A GCS lifecycle policy can
expire run folders older than N days.

BigQuery load
-------------
A single BQ load job targets the wildcard
    gs://…/{run_id}/year=*/month=*/data.parquet
BQ routes each row into the correct monthly partition by reading the
``startDate`` column directly from the Parquet data — no
hive_partitioning_options needed.

Selective month reload (ad-hoc)
--------------------------------
To reload a single broken month without touching other partitions:
    source_uri = "gs://bitziv_health_data/clinical_trials_gov_stg"
                 "/{run_id}/year=2024/month=03/data.parquet"
    table_ref  = "…clinical_trials_gov_stg$202403"   # partition decorator
    disposition = WRITE_TRUNCATE
"""
from __future__ import annotations

import io
import logging

from typing import Literal, Optional

import pyarrow as pa
import pandas as pd
import dask.dataframe as dd
import pyarrow.parquet as pq
from google.cloud import bigquery, storage

from src.config import settings

logger = logging.getLogger(__name__)

WriteDisposition = Literal["WRITE_TRUNCATE", "WRITE_APPEND"]

PARQUET_SCHEMA = pa.schema([
    pa.field("references", pa.list_(
        pa.struct([
            pa.field("citation", pa.string()),
            pa.field("type", pa.string()),
            pa.field("pmid", pa.int64())
        ])
    )),

    pa.field("lastUpdatePostDate", pa.date32()),
    pa.field("startDate", pa.date32()),
    pa.field("completionDate", pa.date32()),
    pa.field("primaryCompletionDate", pa.date32()),

    pa.field("eligibilityCriteria_minimumAge", pa.string()),
    pa.field("organization", pa.string()),
    pa.field("overallStatus", pa.string()),

    pa.field("outcomesModule_primaryOutcomes", pa.list_(
        pa.struct([
            pa.field("timeFrame", pa.string()),
            pa.field("description", pa.string()),
            pa.field("measure", pa.string())
        ])
    )),

    pa.field("armsInterventionsModule_interventions", pa.list_(
        pa.struct([
            pa.field("description", pa.string()),
            pa.field("type", pa.string()),
            pa.field("name", pa.string())
        ])
    )),

    pa.field("designModule_enrollmentInfo_count", pa.int64()),
    pa.field("eligibilityCriteria_stdAges", pa.list_(pa.string())),
    pa.field("designModule_designInfo_maskingInfo_masking", pa.string()),
    pa.field("designModule_designInfo_interventionModel", pa.string()),
    pa.field("conditionsModule", pa.list_(pa.string())),
    pa.field("eligibilityCriteria", pa.string()),
    pa.field("designModule_designInfo_primaryPurpose", pa.string()),
    pa.field("detailedDescription", pa.string()),
    pa.field("leadSponsorCollaborators", pa.list_(pa.string())),
    pa.field("investigatorFullName", pa.string()),
    pa.field("eligibilityCriteria_sex", pa.string()),
    pa.field("designModule_designInfo_allocation", pa.string()),
    pa.field("officialTitle", pa.string()),
    pa.field("eligibilityCriteria_healthyVolunteers", pa.bool_()),

    pa.field("outcomesModule_secondaryOutcomes", pa.list_(
        pa.struct([
            pa.field("timeFrame", pa.string()),
            pa.field("description", pa.string()),
            pa.field("measure", pa.string())
        ])
    )),

    pa.field("designModule_studyType", pa.string()),
    pa.field("leadSponsorName", pa.string()),
    pa.field("nct_id", pa.string()),
])
# ── GCS upload ────────────────────────────────────────────────────────────────

def _upload_chunk_to_gcs(
    trials: list,
    run_id: str,
    chunk_idx: int,
) -> None:
    """
    Serialize all trials in this chunk to a single Parquet file and upload.

    GCS path: {prefix}/{run_id}/chunk_{chunk_idx:04d}.parquet
    BQ wildcard: {prefix}/{run_id}/chunk_*.parquet  (single *, BQ-compatible)

    BQ routes each row to the correct monthly partition via the ``startDate``
    column in the data — the GCS directory structure is irrelevant for that.
    """
    # Input: list of dicts
    pdf = pd.DataFrame(trials)
    ddf = dd.from_pandas(pdf, npartitions=1)
    # 1. Define a directory path, not a filename
    # Remove the .parquet extension from the blob_name itself
    output_path = f"gs://{settings.gcs_bucket}/{settings.gcs_prefix}/{run_id}/chunk_{chunk_idx:04d}"

    # 2. Use storage_options for the project ID
    ddf.to_parquet(
        output_path,
        engine="pyarrow",
        write_index=False,
        schema=PARQUET_SCHEMA,
        # This creates the '_metadata' file BigQuery loves
        write_metadata_file=True,
        overwrite=True,
        # MUST provide project info for GCS access
        storage_options={"project": settings.gcp_project_id} 
    )

    logger.info(
        "Uploaded gs://%s/%s  (%d rows)",
        settings.gcs_bucket,
        output_path,
        len(trials),
    )


# ── BigQuery load job ──────────────────────────────────────────────────────────

def _bq_load_from_gcs(wildcard_uri: str, write_disposition: WriteDisposition) -> Optional[int]:
    """
    Trigger a BigQuery load job that reads all Parquet files matching
    *wildcard_uri* and loads them into the staging table.

    BQ reads ``startDate`` from each row and routes it to the correct
    monthly partition automatically — no hive_partitioning_options needed.
    """
    bq_client = bigquery.Client(project=settings.gcp_project_id)
    table_ref = bigquery.TableReference.from_string(settings.bq_full_table_id)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=getattr(bigquery.WriteDisposition, write_disposition),
        autodetect=False,
    )

    load_job = bq_client.load_table_from_uri(
        wildcard_uri, table_ref, job_config=job_config
    )
    logger.info(
        "BQ load job started: %s  |  uri=%s  |  disposition=%s",
        load_job.job_id,
        wildcard_uri,
        write_disposition,
    )

    load_job.result()

    destination = bq_client.get_table(table_ref)
    logger.info(
        "BQ load job complete: %s  |  table now has %d rows",
        load_job.job_id,
        destination.num_rows,
    )
    return load_job.output_rows


# ── Public API ─────────────────────────────────────────────────────────────────

def upload_trials_chunk_to_gcs(
    trials: list,
    run_id: str,
    chunk_idx: int,
) -> None:
    """
    Serialize *trials* to a single Parquet file and upload to GCS.

    Call once per streaming chunk.  All chunks share the same *run_id* folder;
    *chunk_idx* gives each file a unique name so no chunk overwrites another.

    A separate ``bq_load_trials`` call loads the whole run once all chunks
    are uploaded.
    """
    if not trials:
        logger.debug("upload_trials_chunk: empty list for chunk %d — skipping", chunk_idx)
        return
    _upload_chunk_to_gcs(trials, run_id, chunk_idx)


def bq_load_trials(
    run_id: str,
    write_disposition: WriteDisposition,
) -> Optional[int]:
    """
    Trigger a single BigQuery load job that reads all Parquet files uploaded
    for *run_id*.

    Uses a single-wildcard URI (chunk_*.parquet) which BQ supports.
    Call once after all chunks have been uploaded via ``upload_trials_chunk_to_gcs``.
    """
    wildcard_uri = (
        f"gs://{settings.gcs_bucket}/{settings.gcs_prefix}/{run_id}/chunk_*.parquet"
    )
    return _bq_load_from_gcs(wildcard_uri, write_disposition)

from __future__ import annotations
 
import logging
from dataclasses import dataclass
from datetime import date
from typing import  Optional
 
from google.cloud import bigquery
from google.cloud.bigquery import (
    Client,
    LoadJobConfig,
    SourceFormat,
    WriteDisposition,
)
from src.schemas.tables import TableConfig
from src.config import settings

logger = logging.getLogger(__name__)



# ─── Step 1: Load Parquet from GCS into a staging table ──────────────────────
 
def _load_to_staging(
    client: Client,
    bucket: str,
    prefix: str,
    gcs_subdir: str,
    ingestion_date: date,
    project: str,
    dataset: str,
    batch_id: str,
) -> str:
    """
    Load all Parquet files under
        gs://{bucket}/{prefix}/{gcs_subdir}/ingestion_date=YYYY-MM-DD/
    into a temporary BQ table, fully replacing its contents.
 
    Returns the fully-qualified staging table ID.
    """
    parquet_options = bigquery.ParquetOptions()
    parquet_options.enable_list_inference = True
  
    staging_table = (
        f"{project}.{dataset}._stg_{gcs_subdir}_{ingestion_date.strftime('%Y%m%d')}_{batch_id}"
    )
    source_uri = (
        f"gs://{bucket}/{prefix.rstrip('/')}/{gcs_subdir}/"
        f"ingestion_date={ingestion_date.isoformat()}/batch_{batch_id}/*.parquet"
    )
    logger.info("Loading Parquet from %s into staging table %s", source_uri, staging_table)
 
    job_config = LoadJobConfig(
        source_format=SourceFormat.PARQUET,
        write_disposition=WriteDisposition.WRITE_TRUNCATE,
        # Parquet carries the schema; no autodetect needed.
        parquet_options=parquet_options,
    )
 
    job = client.load_table_from_uri(source_uri, staging_table, job_config=job_config)
    job.result()  # waits for completion, raises on failure
 
    logger.info(
        "Loaded %s rows into %s from %s",
        job.output_rows, staging_table, source_uri,
    )
    return staging_table

def _merge_trial(
    client: Client,
    staging_table: str,
    curated_table: str,
) -> None:
    """
    MERGE staging → curated for the parent 'trial' table.
    Latest `ingested_at` wins on key collision. Inserts new nct_ids.
    """
    # Build the UPDATE SET clause from the curated table's schema (excludes nct_id).
    table = client.get_table(curated_table)
    update_cols = [f.name for f in table.schema if f.name != "nct_id"]
    update_set = ",\n    ".join(f"`{c}` = s.`{c}`" for c in update_cols)
 
    sql = f"""
    MERGE INTO `{curated_table}` t
    USING (
      SELECT *
      FROM `{staging_table}`
      -- If the same nct_id appears multiple times in one batch (shouldn't,
      -- but guard anyway), keep only the freshest.
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY nct_id ORDER BY ingested_at DESC
      ) = 1
    ) s
    ON t.nct_id = s.nct_id
    WHEN MATCHED AND s.ingested_at > t.ingested_at THEN
      UPDATE SET
        {update_set}
    WHEN NOT MATCHED THEN
      INSERT ROW
    """
 
    job = client.query(sql)
    job.result()
    stats = job.num_dml_affected_rows
    logger.info("MERGE %s -> %s affected %s rows", staging_table, curated_table, stats)
    
 
def _replace_children(
    client: Client,
    staging_table: str,
    curated_table: str,
) -> None:
    """
    For child tables (many rows per nct_id), the freshest batch entirely
    replaces prior rows for any nct_id present in the batch.
 
    Runs as a single transaction:
      DELETE FROM curated WHERE nct_id IN (SELECT nct_id FROM staging);
      INSERT INTO curated SELECT * FROM staging;
    """
    # Generate explicit column list from the curated schema.
    # This makes INSERT name-based instead of position-based.
    table = client.get_table(curated_table)
    cols = [f.name for f in table.schema]
    col_list = ", ".join(f"`{c}`" for c in cols)

    sql = f"""
    BEGIN TRANSACTION;

    DELETE FROM `{curated_table}`
    WHERE nct_id IN (SELECT DISTINCT nct_id FROM `{staging_table}`);

    INSERT INTO `{curated_table}` ({col_list})
    SELECT {col_list} FROM `{staging_table}`;

    COMMIT TRANSACTION;
    """
 
    job = client.query(sql)
    job.result()
    logger.info("Replaced child rows in %s from %s using %s", curated_table, staging_table, col_list)
    
# ─── Cleanup ─────────────────────────────────────────────────────────────────
 
def _drop_staging(client: Client, staging_table: str) -> None:
    client.delete_table(staging_table, not_found_ok=True)
    logger.info("Dropped staging table %s", staging_table)
    
# ─── Orchestrator ────────────────────────────────────────────────────────────
 
def load_batch_to_bigquery(
    bucket: str,
    prefix: str,
    ingestion_date: date,
    batch_id: str,
    project: str,
    dataset: str,
    table_configs: tuple[TableConfig, ...],
    client: Optional[Client] = None,
    drop_staging_after: bool = True,
) -> None:
    """
    Run the full Parquet → staging → curated pipeline for all seven tables
    for a given ingestion_date.
 
    Tables are processed sequentially; each landing/merge waits for the
    previous to finish. Failures raise; partial state is allowed (a failed
    child merge does not roll back a successful parent merge — each is
    its own transaction). Re-running the orchestrator for the same date
    is safe and idempotent.
    """
    if client is None:
        client = bigquery.Client(project=project)
 
    logger.info(
        "Starting BQ load: project=%s dataset=%s ingestion_date=%s batch_id=%s",
        project, dataset, ingestion_date, batch_id,
    )
 
    for cfg in table_configs:
        curated = f"{project}.{dataset}.{cfg.curated_table}"
 
        try:
            staging = _load_to_staging(
                client=client,
                bucket=bucket,
                prefix=prefix,
                gcs_subdir=cfg.gcs_subdir,
                ingestion_date=ingestion_date,
                project=project,
                dataset=dataset,
                batch_id=batch_id,
            )
        except Exception as e:
            # If there are no files for this table for this date (e.g., the
            # batch happened to contain no trials with locations), skip it.
            if "Not found" in str(e) or "does not match any" in str(e):
                logger.warning("No Parquet for %s on %s — skipping", cfg.gcs_subdir, ingestion_date)
                continue
            raise
 
        try:
            if cfg.strategy == "upsert_on_nct_id":
                _merge_trial(client, staging, curated)
            else:
                _replace_children(client, staging, curated)
        finally:
            if drop_staging_after:
                _drop_staging(client, staging)
 
    logger.info("Completed BQ load for ingestion_date=%s", ingestion_date)

def get_existing_embeddings_hash( nct_ids: list[str],
                                gcp_project: str = settings.gcp_project_id,
                                dataset: str = settings.bq_dataset,
                                table: str = settings.bq_embeddings_table,
                                client: Optional[Client] = None) -> dict[tuple[str, str, int], str]:
    """
    For a list of nct_ids, return a dict mapping nct_id -> source_hash for all
    existing embeddings. This allows the caller to skip embedding chunks that
    haven't changed since the last run.
    """
    if not nct_ids:
        return {}
    if client is None:
        client = bigquery.Client()
 
    sql = f"""
    SELECT nct_id, field_type, chunk_id, source_hash
    FROM `{gcp_project}.{dataset}.{table}`
    WHERE nct_id IN UNNEST(@nct_ids)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("nct_ids", "STRING", nct_ids),
        ],
    )
 
    query_job = client.query(sql, job_config=job_config)
    results = query_job.result()

    return {(row.nct_id, row.field_type, row.chunk_id): row.source_hash for row in results}


def get_existing_eligibility_hash(
    nct_ids: list[str],
    gcp_project: str = settings.gcp_project_id,
    dataset: str = settings.bq_dataset,
    table: str = settings.bq_eligibility_table,
    client: Optional[Client] = None,
) -> dict[str, str]:
    """For a list of nct_ids, return {nct_id: source_hash} of already-extracted eligibility.

    One hash per trial (the hash of the whole eligibility blob). Lets the caller skip the
    LLM call for trials whose eligibility text is unchanged — the dominant backfill cost.
    Returns {} if the table doesn't exist yet (first run).
    """
    if not nct_ids:
        return {}
    if client is None:
        client = bigquery.Client()

    sql = f"""
    SELECT nct_id, ANY_VALUE(source_hash) AS source_hash
    FROM `{gcp_project}.{dataset}.{table}`
    WHERE nct_id IN UNNEST(@nct_ids)
    GROUP BY nct_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("nct_ids", "STRING", nct_ids)],
    )
    try:
        results = client.query(sql, job_config=job_config).result()
    except Exception as exc:
        logger.warning("Could not read existing eligibility hashes (%s) — extracting all", exc)
        return {}

    return {row.nct_id: row.source_hash for row in results}
    
"""
Prefect flow: clinicalTrials.gov → GCS (Parquet) → BigQuery.

Two sub-flows run in sequence per run:
  1. clinical_trials_etl_flow   — trial data  → clinical_trials_gov_stg
  2. embeddings embedded inline  — text chunks → clinical_trials_gov_embeddings_stg

Usage
-----
Full load (truncate both staging tables and reload everything):
    python -m flows.clinical_trials_flow --full-load

Incremental (append studies updated since the last BQ watermark):
    python -m flows.clinical_trials_flow

Override date window explicitly:
    python -m flows.clinical_trials_flow \\
        --from-date 2024-01-01 --to-date 2024-06-30

Skip embedding generation (data load only):
    python -m flows.clinical_trials_flow --skip-embeddings

Prefect deployment (daily at 02:00 UTC):
    prefect deploy pipelines/etl/flows/clinical_trials_flow.py:clinical_trials_etl_flow \\
        --name clinical-trials-daily \\
        --cron "0 2 * * *"
"""
from __future__ import annotations

import argparse
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from google.cloud import bigquery
from prefect import flow, get_run_logger, task
from prefect.tasks import exponential_backoff

from src.config import settings
from src.schemas.tables import (
    ELIGIBILITY_TABLE_CONFIG,
    EMBEDDING_TABLE_CONFIG,
    TABLE_CONFIGS,
)
from src.set_logger import configure_logging
from src.tasks.extract import extract_studies_streaming
from src.tasks.load.gcs_load import (
    upload_eligibility_batch,
    upload_embeddings_batch,
    upload_studies_batch,
)
from src.tasks.load.bq import load_batch_to_bigquery
from src.tasks.load.pg import (
    upsert_eligibility_criteria,
    upsert_trials,
    upsert_embeddings,
)
from src.tasks.transform.eligibility_extract import extract_trials
from src.tasks.transform.embed import get_embedder
from src.tasks.transform.transform_studies import transform_studies

# ── Prefect tasks ──────────────────────────────────────────────────────────────


@task(
    name="get-bq-watermark",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def get_watermark() -> Optional[date]:
    """
    Return the MAX(lastUpdatePostDate) from the staging table, or ``None``
    if the table is empty / doesn't exist yet.
    """
    logger = get_run_logger()
    client = bigquery.Client(project=settings.gcp_project_id)
    query = f"SELECT MAX(lastUpdatePostDate) AS watermark FROM `{settings.bq_full_table_id}`"
    try:
        rows = list(client.query(query).result())
        watermark = rows[0].watermark if rows else None
        logger.info("BQ watermark: %s", watermark)
        return watermark
    except Exception as exc:
        logger.warning("Could not read BQ watermark (%s) — will fall back to 30-day window", exc)
        return None


@task(name="transform-clinical-trials")
def transform_task(raw_studies: list[dict]):
    logger = get_run_logger()
    trials = transform_studies(raw_studies)
    logger.info("Transformed %d valid trials", len(trials))
    return trials


@task(
    name="upload-trials-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def gcs_upload_trials_chunk_task(trials, run_id: str, chunk_idx: int, ingested_at: date) -> int:
    upload_studies_batch(transformed_studies=trials, bucket_name=settings.gcs_bucket, chunk_idx=chunk_idx, prefix=settings.gcs_prefix, batch_id=run_id, ingestion_date=ingested_at)
    return len(trials)

@task(
    name="upload-embeddings-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def gcs_upload_embeddings_chunk_task(embeddings, run_id: str, chunk_idx: int, ingested_at: date) -> int:
    upload_embeddings_batch(embeddings=embeddings, bucket_name=settings.gcs_bucket, chunk_idx=chunk_idx, prefix=settings.gcs_embeddings_prefix, batch_id=run_id, ingestion_date=ingested_at)
    return len(embeddings)


@task(
    name="embeddings-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def embeddings_chunk_task(
    transformed_studies: list[dict],
    skip_existing_check: bool = False,
    eligibility_rows: Optional[list[dict]] = None,
) -> list[dict]:
    return get_embedder().embed_trials(
        transformed_studies,
        skip_existing_check=skip_existing_check,
        eligibility_rows=eligibility_rows,
    )


@task(
    name="eligibility-extract-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def eligibility_extract_chunk_task(
    transformed_studies: list[dict],
    ingestion_date: date,
    skip_existing_check: bool = False,
) -> list[dict]:
    return extract_trials(
        transformed_studies,
        ingestion_date=ingestion_date,
        skip_existing_check=skip_existing_check,
    )


@task(
    name="upload-eligibility-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def gcs_upload_eligibility_chunk_task(eligibility_rows, run_id: str, chunk_idx: int, ingested_at: date) -> int:
    upload_eligibility_batch(eligibility_rows=eligibility_rows, bucket_name=settings.gcs_bucket, chunk_idx=chunk_idx, prefix=settings.gcs_eligibility_prefix, batch_id=run_id, ingestion_date=ingested_at)
    return len(eligibility_rows)


@task(
    name="pg-upsert-eligibility",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def pg_upsert_eligibility_task(eligibility_rows: list[dict]) -> int:
    if not settings.pg_database_url:
        return 0
    return upsert_eligibility_criteria(
        eligibility_rows=eligibility_rows,
        database_url=settings.pg_database_url,
    )


@task(
    name="bq-load-eligibility",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def bq_load_eligibility_task(run_id: str, ingestion_date: date) -> Optional[int]:
    load_batch_to_bigquery(
        bucket=settings.gcs_bucket,
        prefix=settings.gcs_eligibility_prefix,
        ingestion_date=ingestion_date,
        batch_id=run_id,
        project=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_configs=ELIGIBILITY_TABLE_CONFIG,
    )


@task(
    name="pg-upsert-trials",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def pg_upsert_trials_task(trials: list[dict], ingestion_date: date, ingested_at: datetime) -> int:
    if not settings.pg_database_url:
        return 0
    return upsert_trials(
        transformed_studies=trials,
        ingestion_date=ingestion_date,
        database_url=settings.pg_database_url,
        ingested_at=ingested_at,
    )


@task(
    name="pg-upsert-embeddings",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def pg_upsert_embeddings_task(embeddings: list[dict]) -> int:
    if not settings.pg_database_url:
        return 0
    return upsert_embeddings(
        embeddings=embeddings,
        database_url=settings.pg_database_url,
    )


@task(
    name="bq-load-trials",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def bq_load_trials_task(run_id: str, ingestion_date: date) -> Optional[int]:
    load_batch_to_bigquery(
        bucket=settings.gcs_bucket,
        prefix=settings.gcs_prefix,
        ingestion_date=ingestion_date,
        batch_id=run_id,
        project=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_configs=TABLE_CONFIGS,
    )


@task(
    name="bq-load-embeddings",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def bq_load_embeddings_task(run_id: str, ingestion_date: date) -> Optional[int]:
    load_batch_to_bigquery(
        bucket=settings.gcs_bucket,
        prefix=settings.gcs_embeddings_prefix,
        ingestion_date=ingestion_date,
        batch_id=run_id,
        project=settings.gcp_project_id,
        dataset=settings.bq_dataset,
        table_configs=EMBEDDING_TABLE_CONFIG,
    )


# ── Main flow ──────────────────────────────────────────────────────────────────


@flow(
    name="clinical-trials-etl",
    description=(
        "Fetch studies from clinicalTrials.gov v2 API, write Parquet to GCS, "
        "load trial data into clinical_trials_gov_stg, then generate Vertex AI "
        "embeddings and load into clinical_trials_gov_embeddings_stg."
    ),
    log_prints=True,
)
def clinical_trials_etl_flow(
    full_load: bool = False,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    skip_embeddings: bool = False,
    skip_eligibility: bool = False,
    skip_existing_check: bool = False,
):
    """
    Parameters
    ----------
    full_load:
        ``from_date`` (default 2000-01-01).
    from_date:
        ISO date ``YYYY-MM-DD``.  Overrides the watermark / default start.
    to_date:
        ISO date ``YYYY-MM-DD``.  Defaults to today.
    skip_embeddings:
        Set ``True`` to only load trial data without generating embeddings
        (useful for quick backfills or debugging).
    skip_eligibility:
        Set ``True`` to skip structured-eligibility extraction (the LLM step).
        It is also skipped automatically when no OpenAI key is configured.
    """
    logger = get_run_logger()
    
    # ── Resolve date window ────────────────────────────────────────────────────
    end: date = date.fromisoformat(to_date) if to_date else date.today()
    if full_load:
        start: date = date.fromisoformat(from_date) if from_date else date(2000, 1, 1)
        logger.info("Mode: FULL LOAD  |  %s → %s", start, end)
    else:
        if from_date:
            start = date.fromisoformat(from_date)
        else:
            watermark = get_watermark()
            start = (watermark + timedelta(days=1)) if watermark else (end - timedelta(days=30))
        logger.info("Mode: INCREMENTAL  |  %s → %s", start, end)

    if start > end:
        logger.info("start (%s) > end (%s) — nothing to do", start, end)
        return {"trials_loaded": 0, "embedding_rows_loaded": 0}

    run_id = f"{start.isoformat()}_{end.isoformat()}_{uuid.uuid4().hex[:8]}"

    # ── Stages 1 & 2: Stream one date-range chunk at a time ───────────────────
    # Each chunk (~90 days of studies) is extracted, transformed, serialised to
    # Parquet, and uploaded to GCS before the next chunk is fetched.  Only one
    # chunk's data lives in RAM at a time, so full-load runs (400k+ studies)
    # no longer risk OOM.  A single BQ load job runs after all chunks are done.
    total_trials = 0
    total_embedding_chunks = 0
    total_eligibility_rows = 0
    embed_chunk_idx = 0
    elig_chunk_idx = 0
    ingested_at = datetime.now(timezone.utc).date()
    ingested_at_dt = datetime.now(timezone.utc)
    # Eligibility runs only when an LLM is configured (the extractor no-ops otherwise).
    run_eligibility = not skip_eligibility and bool(settings.openai_api_key)
    trial_batch_size = settings.embedding_trial_batch_size
    for chunk_idx, raw_chunk in enumerate(extract_studies_streaming(start, end)):
        trials = transform_task(raw_chunk)
        uploaded = gcs_upload_trials_chunk_task(trials, run_id=run_id, chunk_idx=chunk_idx, ingested_at=ingested_at)
        total_trials += uploaded
        pg_upsert_trials_task(trials, ingestion_date=ingested_at, ingested_at=ingested_at_dt)
        # One sub-batch loop: extract structured eligibility FIRST, then embed — the
        # extracted items are fed into the same embeddings batch (per-item eligibility
        # vectors ride with the trial's other chunks, so replace-by-nct_id stays correct).
        for sub_idx in range(0, len(trials), trial_batch_size):
            sub_batch = trials[sub_idx : sub_idx + trial_batch_size]

            eligibility_rows: list[dict] = []
            if run_eligibility:
                eligibility_rows = eligibility_extract_chunk_task(
                    sub_batch, ingestion_date=ingested_at,
                    skip_existing_check=full_load or skip_existing_check,
                )
                if eligibility_rows:
                    gcs_upload_eligibility_chunk_task(eligibility_rows, run_id=run_id, chunk_idx=elig_chunk_idx, ingested_at=ingested_at)
                    total_eligibility_rows += len(eligibility_rows)
                    pg_upsert_eligibility_task(eligibility_rows)
                elig_chunk_idx += 1

            if not skip_embeddings:
                embeddings = embeddings_chunk_task(
                    sub_batch,
                    skip_existing_check=full_load or skip_existing_check,
                    eligibility_rows=eligibility_rows,
                )
                gcs_upload_embeddings_chunk_task(embeddings, run_id=run_id, chunk_idx=embed_chunk_idx, ingested_at=ingested_at)
                total_embedding_chunks += len(embeddings)
                embed_chunk_idx += 1
                pg_upsert_embeddings_task(embeddings)

    if skip_embeddings:
        logger.info("Skipping embedding generation (--skip-embeddings)")
    if not run_eligibility:
        logger.info("Skipping eligibility extraction (--skip-eligibility or no OpenAI key)")

    # ── Stage 3: Single BQ load per table ─────────────────────────────────────
    bq_load_trials_task(run_id, ingested_at) if total_trials else 0

    if not skip_embeddings and total_embedding_chunks:
        bq_load_embeddings_task(run_id, ingested_at)

    if run_eligibility and total_eligibility_rows:
        bq_load_eligibility_task(run_id, ingested_at)

    logger.info("Flow complete: run_id=%s", run_id)


# ── CLI entry-point ────────────────────────────────────────────────────────────
configure_logging(settings)  # Must be called at the module level to set up logging for all tasks and flows
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the clinical trials ETL flow locally.")
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Truncate both staging tables and reload all data (default: incremental).",
    )
    parser.add_argument("--from-date", metavar="YYYY-MM-DD", help="Override start date.")
    parser.add_argument("--to-date", metavar="YYYY-MM-DD", help="Override end date (default: today).")
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Load trial data only, skip embedding generation.",
    )
    parser.add_argument(
        "--skip-eligibility",
        action="store_true",
        help="Skip structured-eligibility LLM extraction (also auto-skipped without an OpenAI key).",
    )
    parser.add_argument(
        "--skip-existing-check",
        action="store_true",
        help="Skip BQ hash lookup and embed/extract all unconditionally. Useful for test runs and initial loads.",
    )
    args = parser.parse_args()

    clinical_trials_etl_flow(
        full_load=args.full_load,
        from_date=args.from_date,
        to_date=args.to_date,
        skip_embeddings=args.skip_embeddings,
        skip_eligibility=args.skip_eligibility,
        skip_existing_check=args.skip_existing_check,
    )

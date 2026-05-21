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
from datetime import date, timedelta
from typing import Optional

from google.cloud import bigquery
from prefect import flow, get_run_logger, task
from prefect.tasks import exponential_backoff

from src.config import settings
from src.tasks.embed import (
    generate_trial_chunks,
    upload_embeddings_chunk_to_gcs,
    bq_load_embeddings,
)
from src.tasks.extract import extract_studies_streaming
from src.tasks.load import upload_trials_chunk_to_gcs, bq_load_trials
from src.tasks.transform import transform_studies

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
def upload_trials_chunk_task(trials, run_id: str, chunk_idx: int) -> int:
    upload_trials_chunk_to_gcs(trials, run_id, chunk_idx)
    return len(trials)


@task(
    name="generate-embeddings",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def generate_embeddings_task(trials):
    logger = get_run_logger()
    chunks = generate_trial_chunks(trials)
    logger.info("Generated %d embedding chunks from %d trials", len(chunks), len(trials))
    return chunks


@task(
    name="upload-embeddings-chunk",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def upload_embeddings_chunk_task(chunks, run_id: str, chunk_idx: int) -> int:
    upload_embeddings_chunk_to_gcs(chunks, run_id, chunk_idx)
    return len(chunks)


@task(
    name="bq-load-trials",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def bq_load_trials_task(run_id: str, write_disposition: str) -> Optional[int]:
    logger = get_run_logger()
    rows = bq_load_trials(run_id, write_disposition)  # type: ignore[arg-type]
    logger.info("Loaded %d rows → %s  (disposition=%s)", rows, settings.bq_full_table_id, write_disposition)
    return rows


@task(
    name="bq-load-embeddings",
    retries=2,
    retry_delay_seconds=exponential_backoff(backoff_factor=2),
)
def bq_load_embeddings_task(run_id: str, write_disposition: str) -> Optional[int]:
    logger = get_run_logger()
    rows = bq_load_embeddings(run_id, write_disposition)  # type: ignore[arg-type]
    logger.info("Loaded %d embedding rows → %s.%s", rows, settings.bq_dataset, settings.bq_embeddings_table)
    return rows


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
) -> dict:
    """
    Parameters
    ----------
    full_load:
        ``True`` → WRITE_TRUNCATE both staging tables and reload from
        ``from_date`` (default 2000-01-01).
        ``False`` (default) → incremental append since the BQ watermark.
    from_date:
        ISO date ``YYYY-MM-DD``.  Overrides the watermark / default start.
    to_date:
        ISO date ``YYYY-MM-DD``.  Defaults to today.
    skip_embeddings:
        Set ``True`` to only load trial data without generating embeddings
        (useful for quick backfills or debugging).

    Returns
    -------
    dict with keys ``trials_loaded`` and ``embedding_rows_loaded``.
    """
    logger = get_run_logger()

    # ── Resolve date window ────────────────────────────────────────────────────
    end: date = date.fromisoformat(to_date) if to_date else date.today()

    if full_load:
        start: date = date.fromisoformat(from_date) if from_date else date(2000, 1, 1)
        write_disposition = "WRITE_TRUNCATE"
        logger.info("Mode: FULL LOAD  |  %s → %s", start, end)
    else:
        if from_date:
            start = date.fromisoformat(from_date)
        else:
            watermark = get_watermark()
            start = (watermark + timedelta(days=1)) if watermark else (end - timedelta(days=30))
        write_disposition = "WRITE_APPEND"
        logger.info("Mode: INCREMENTAL  |  %s → %s", start, end)

    if start > end:
        logger.info("start (%s) > end (%s) — nothing to do", start, end)
        return {"trials_loaded": 0, "embedding_rows_loaded": 0}

    run_id = f"{end.isoformat()}_{write_disposition.lower()}_{uuid.uuid4().hex[:8]}"

    # ── Stages 1 & 2: Stream one date-range chunk at a time ───────────────────
    # Each chunk (~90 days of studies) is extracted, transformed, serialised to
    # Parquet, and uploaded to GCS before the next chunk is fetched.  Only one
    # chunk's data lives in RAM at a time, so full-load runs (400k+ studies)
    # no longer risk OOM.  A single BQ load job runs after all chunks are done.
    total_trials = 0
    total_embedding_chunks = 0

    for chunk_idx, raw_chunk in enumerate(extract_studies_streaming(start, end)):
        trials = transform_task(raw_chunk)
        uploaded = upload_trials_chunk_task(trials, run_id, chunk_idx)
        total_trials += uploaded

        if not skip_embeddings:
            emb_chunks = generate_embeddings_task(trials)
            uploaded_emb = upload_embeddings_chunk_task(emb_chunks, run_id, chunk_idx)
            total_embedding_chunks += uploaded_emb

    if skip_embeddings:
        logger.info("Skipping embedding generation (--skip-embeddings)")

    # ── Stage 3: Single BQ load per table ─────────────────────────────────────
    trials_loaded = bq_load_trials_task(run_id, write_disposition) if total_trials else 0

    embedding_rows_loaded = 0
    if not skip_embeddings and total_embedding_chunks:
        embedding_rows_loaded = bq_load_embeddings_task(run_id, write_disposition)

    result = {
        "trials_loaded": trials_loaded,
        "embedding_rows_loaded": embedding_rows_loaded,
    }
    logger.info("Flow complete: %s  |  run_id=%s", result, run_id)
    return result


# ── CLI entry-point ────────────────────────────────────────────────────────────

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
    args = parser.parse_args()

    clinical_trials_etl_flow(
        full_load=args.full_load,
        from_date=args.from_date,
        to_date=args.to_date,
        skip_embeddings=args.skip_embeddings,
    )

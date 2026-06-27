from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import create_engine, delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ctiq_db.models import (
    ClinicalTrial,
    EligibilityBatchJob,
    TrialArmGroup,
    TrialEligibilityCriterion,
    TrialEmbedding,
    TrialIntervention,
    TrialLocation,
    TrialMeshTerm,
    TrialOfficial,
    TrialOutcome,
)

# Batch-job statuses that still need attention (status check and/or ingest). Terminal
# states (ingested/failed/expired/cancelled) are excluded.
_ACTIVE_BATCH_STATUSES = ("submitted", "in_progress", "completed")

logger = logging.getLogger(__name__)

_CHILD_TABLE_MAP = [
    (TrialLocation,     "locations"),
    (TrialMeshTerm,     "mesh_terms"),
    (TrialArmGroup,     "arm_groups"),
    (TrialIntervention, "interventions"),
    (TrialOutcome,      "outcomes"),
    (TrialOfficial,     "officials"),
]

# Keep VALUES clause size manageable for large chunks.
_BATCH_SIZE = 500


def _batched(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def _trial_upsert(batch: list[dict]):
    stmt = pg_insert(ClinicalTrial).values(batch)
    update_cols = {
        c.key: stmt.excluded[c.key]
        for c in ClinicalTrial.__table__.c
        if c.key != "nct_id"
    }
    # Only overwrite when the incoming row is strictly newer.
    return stmt.on_conflict_do_update(
        index_elements=["nct_id"],
        set_=update_cols,
        where=ClinicalTrial.ingested_at < stmt.excluded.ingested_at,
    )




def upsert_trials(
    transformed_studies: list[dict],
    ingestion_date: date,
    database_url: str,
    ingested_at: Optional[datetime] = None,
) -> int:
    """
    Upsert one ETL chunk of transformed trials into Postgres.

    Parent table  → INSERT ... ON CONFLICT DO UPDATE (newer ingested_at wins).
    Child tables  → DELETE WHERE nct_id IN (...) then bulk INSERT.
    Both run in a single transaction so a failed child insert rolls back the parent.

    Returns the number of trial rows processed.
    """
    if not transformed_studies:
        return 0

    if ingested_at is None:
        ingested_at = datetime.now(timezone.utc)

    trial_rows: list[dict] = []
    child_rows: dict[str, list[dict]] = {key: [] for _, key in _CHILD_TABLE_MAP}
    nct_ids: list[str] = []

    for study in transformed_studies:
        if not study:
            continue
        trial = study["trial"]
        nct_ids.append(trial["nct_id"])
        trial_rows.append({**trial, "ingestion_date": ingestion_date, "ingested_at": ingested_at})
        for _, key in _CHILD_TABLE_MAP:
            for row in (study.get(key) or []):
                child_rows[key].append({**row, "ingestion_date": ingestion_date})

    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            for batch in _batched(trial_rows, _BATCH_SIZE):
                conn.execute(_trial_upsert(batch))

            for model, key in _CHILD_TABLE_MAP:
                conn.execute(delete(model).where(model.nct_id.in_(nct_ids)))
                for batch in _batched(child_rows[key], _BATCH_SIZE):
                    conn.execute(pg_insert(model).values(batch))
                logger.info(
                    "Postgres: replaced or inserted %d rows for %s, children for %d nct_ids",
                    len(child_rows[key]), model.__tablename__, len(nct_ids),
                )

        logger.info(
            "Postgres: upserted %d trials",
            len(trial_rows),
        )
    finally:
        engine.dispose()

    return len(trial_rows)


def upsert_embeddings(
    embeddings: list[dict],
    database_url: str,
) -> int:
    """
    Replace embedding rows for the (nct_id, field_type) pairs present in this batch.

    The delete is scoped to the field types actually in the batch — not all of an nct_id's
    embeddings — so independent writers can populate different field types for the same
    trial without clobbering each other (e.g. the batch-mode eligibility path writes
    eligibility_inclusion/_exclusion *after* the trial's title/summary were written in the
    streaming pass). It also stops hash-gating from deleting unchanged-but-skipped chunks.

    Caveat: a field type that disappears entirely for a trial isn't cleared here (it's not
    in the batch). Removing a retired field type (e.g. the old single `eligibility`) is a
    one-time `DELETE ... WHERE field_type = '...'`.

    Returns the number of embedding rows processed.
    """
    if not embeddings:
        return 0

    nct_ids = list({row["nct_id"] for row in embeddings})
    field_types = list({row["field_type"] for row in embeddings})

    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                delete(TrialEmbedding).where(
                    TrialEmbedding.nct_id.in_(nct_ids),
                    TrialEmbedding.field_type.in_(field_types),
                )
            )
            for batch in _batched(embeddings, _BATCH_SIZE):
                conn.execute(pg_insert(TrialEmbedding).values(batch))

        logger.info(
            "Postgres: replaced or inserted embeddings for %d nct_ids, %d field types (%d rows)",
            len(nct_ids), len(field_types), len(embeddings),
        )
    finally:
        engine.dispose()

    return len(embeddings)


def upsert_eligibility_criteria(
    eligibility_rows: list[dict],
    database_url: str,
) -> int:
    """Replace structured-eligibility rows for all affected nct_ids (child-table strategy).

    Deletes existing criteria for nct_ids present in the batch, then inserts the new rows —
    keeps the table consistent when a trial is re-extracted. Trials skipped by the
    source_hash gate aren't in the batch, so their existing rows survive.

    Returns the number of criterion rows processed.
    """
    if not eligibility_rows:
        return 0

    nct_ids = list({row["nct_id"] for row in eligibility_rows})

    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                delete(TrialEligibilityCriterion).where(
                    TrialEligibilityCriterion.nct_id.in_(nct_ids)
                )
            )
            for batch in _batched(eligibility_rows, _BATCH_SIZE):
                conn.execute(pg_insert(TrialEligibilityCriterion).values(batch))

        logger.info(
            "Postgres: replaced or inserted eligibility for %d nct_ids (%d rows)",
            len(nct_ids), len(eligibility_rows),
        )
    finally:
        engine.dispose()

    return len(eligibility_rows)


# ─── Eligibility batch-job tracking (async backfill) ──────────────────────────

def create_batch_job(database_url: str, job: dict) -> None:
    """Persist a submitted OpenAI batch job (status=submitted). `job` is a column dict."""
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(pg_insert(EligibilityBatchJob).values(job))
        logger.info("Postgres: recorded batch job %s (%s requests)",
                    job.get("openai_batch_id"), job.get("request_count"))
    finally:
        engine.dispose()


def get_active_batch_jobs(database_url: str) -> list[dict]:
    """Return non-terminal batch jobs (submitted/in_progress/completed) as plain dicts —
    everything the poller needs to check status and ingest."""
    cols = (
        EligibilityBatchJob.openai_batch_id,
        EligibilityBatchJob.output_file_id,
        EligibilityBatchJob.status,
        EligibilityBatchJob.request_hashes,
        EligibilityBatchJob.ingestion_date,
    )
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                select(*cols).where(EligibilityBatchJob.status.in_(_ACTIVE_BATCH_STATUSES))
            ).all()
    finally:
        engine.dispose()
    return [
        {
            "openai_batch_id": r.openai_batch_id,
            "output_file_id": r.output_file_id,
            "status": r.status,
            "request_hashes": r.request_hashes or {},
            "ingestion_date": r.ingestion_date,
        }
        for r in rows
    ]


def update_batch_job(database_url: str, openai_batch_id: str, **fields) -> None:
    """Patch a batch job row by openai_batch_id (status, *_at timestamps, error, etc.)."""
    if not fields:
        return
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                update(EligibilityBatchJob)
                .where(EligibilityBatchJob.openai_batch_id == openai_batch_id)
                .values(**fields)
            )
    finally:
        engine.dispose()

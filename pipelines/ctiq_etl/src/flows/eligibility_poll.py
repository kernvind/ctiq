"""Prefect flow: poll & ingest async eligibility batch jobs.

The companion to the main flow's --eligibility-mode=batch (which only *submits* + persists
jobs). This flow checks every active job against OpenAI, ingests completed ones into
Postgres (criterion rows + per-item eligibility embeddings), and advances each job's status.

Idempotent and resumable — safe to run repeatedly (e.g. on a cron) until all jobs reach
`ingested`. A job left `completed`-but-not-`ingested` (ingest crashed) is retried next pass.

Usage:
    python -m src.flows.eligibility_poll
"""
from __future__ import annotations

from prefect import flow, get_run_logger

from src.config import settings
from src.set_logger import configure_logging
from src.tasks.transform.eligibility_batch import poll_and_ingest


@flow(name="eligibility-batch-poll", log_prints=True)
def eligibility_poll_flow() -> dict:
    logger = get_run_logger()
    summary = poll_and_ingest()
    logger.info(
        "Eligibility poll complete: checked=%d ingested=%d",
        summary.get("checked", 0), summary.get("ingested", 0),
    )
    return summary


configure_logging(settings)
if __name__ == "__main__":
    eligibility_poll_flow()

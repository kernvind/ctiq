"""Batch-API path for Stage A eligibility extraction (the 590k-backfill tool).

Instead of one synchronous request per trial (eligibility_extract.extract_trials), this
submits an OpenAI **Batch** job: a JSONL of /v1/responses requests processed asynchronously
within 24h at ~50% cost and without rate-limit juggling. Selected via the flow's
--eligibility-mode=batch. Reuses the same schema + prompt as the inline path so output is
identical in shape.

Flow per call: collect_pending → split into ≤max_requests groups → for each group:
submit → poll to completion → parse results → to_db_rows. Blocking (polls until done).

NOTE: the Batch + Responses + structured-output request/response shapes are API-version
sensitive and can't be unit-tested offline here — smoke-test against the live API on a tiny
window before a full backfill. Parsing is defensive about the response envelope.
"""
from __future__ import annotations

import io
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Iterable, Optional

from openai import OpenAI
from openai.types.batch import Batch
from src.config import settings
from src.tasks.transform.eligibility_extract import (
    ExtractedEligibility,
    _SYSTEM_PROMPT,
    collect_pending,
    lupd_map,
    to_db_rows,
)

logger = logging.getLogger(__name__)

_RESPONSES_ENDPOINT = "/v1/responses"


def _batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _text_format_param() -> dict:
    """The Responses `text` param value: ``{"format": {...json_schema...}}`` requesting
    strict structured output of ExtractedEligibility — reusing the SDK's own schema
    conversion so it matches what `responses.parse` sends. The SDK helper returns the inner
    format object, so we wrap it under "format" (the shape the Responses body expects).
    """
    try:  # SDK helper used by responses.parse — returns the inner format object
        from openai.lib._parsing._responses import type_to_text_format_param

        return {"format": type_to_text_format_param(ExtractedEligibility)}
    except Exception:  # fallback: build the json_schema format by hand
        from openai.lib._pydantic import to_strict_json_schema

        return {
            "format": {
                "type": "json_schema",
                "name": "ExtractedEligibility",
                "schema": to_strict_json_schema(ExtractedEligibility),
                "strict": True,
            }
        }


def build_requests(pending: dict[str, tuple[str, str]], model: str) -> list[dict]:
    """One Batch request line per trial. custom_id = nct_id (how we map results back)."""
    text_format = _text_format_param()
    requests: list[dict] = []
    for nct_id, (text, _hash) in pending.items():
        requests.append(
            {
                "custom_id": nct_id,
                "method": "POST",
                "url": _RESPONSES_ENDPOINT,
                "body": {
                    "model": model,
                    "instructions": _SYSTEM_PROMPT,
                    "input": text,
                    "text": text_format,
                },
            }
        )
    return requests


def _create_batch(client: OpenAI, requests: list[dict]) -> tuple[Batch, str]:
    """Upload the JSONL request file and create the batch; return (batch, input_file_id)."""
    buf = io.BytesIO("\n".join(json.dumps(r) for r in requests).encode("utf-8"))
    upload = client.files.create(file=("eligibility_batch.jsonl", buf), purpose="batch")
    batch = client.batches.create(
        input_file_id=upload.id,
        endpoint=_RESPONSES_ENDPOINT,
        completion_window="24h",
    )
    logger.info("Created eligibility batch %s (%d requests)", batch.id, len(requests))
    return batch, upload.id


def _map_status(openai_status: str) -> str:
    """OpenAI batch status → our tracking status (everything non-terminal → in_progress)."""
    if openai_status in ("completed", "failed", "expired", "cancelled"):
        return openai_status
    return "in_progress"


def _iter_request_groups(pending: dict[str, tuple[str, str]]):
    """Yield (group_pending, requests) per batch file, respecting the per-batch request cap."""
    model = settings.eligibility_extract_model
    for chunk in _batched(list(pending.items()), settings.eligibility_batch_max_requests):
        group = dict(chunk)
        yield group, build_requests(group, model)


def _poll(client, batch_id: str, poll_seconds: int, max_wait_seconds: int):
    """Block until the batch reaches a terminal state or we exceed max_wait_seconds."""
    waited = 0
    terminal = {"completed", "failed", "expired", "cancelled"}
    while True:
        batch = client.batches.retrieve(batch_id)
        if batch.status in terminal:
            logger.info("Batch %s reached status=%s", batch_id, batch.status)
            return batch
        if waited >= max_wait_seconds:
            raise TimeoutError(
                f"Batch {batch_id} not done after {waited}s (status={batch.status})"
            )
        time.sleep(poll_seconds)
        waited += poll_seconds


def _output_text(body: dict) -> Optional[str]:
    """Pull the model's JSON text out of a Responses result body, tolerant of shape."""
    if not isinstance(body, dict):
        return None
    if body.get("output_text"):  # convenience field when present
        return body["output_text"]
    for item in body.get("output") or []:  # dig: output[].content[].text
        for part in item.get("content") or []:
            if part.get("type") in ("output_text", "text") and part.get("text"):
                return part["text"]
    return None


def _meta(value) -> tuple[Optional[str], object]:
    """Normalize a per-nct request map value → (source_hash, last_update_post_date).

    Accepts the rich form {"h": hash, "lupd": iso|date} or the legacy bare-hash string
    (jobs submitted before last_update_post_date threading) for backward compatibility.
    """
    if isinstance(value, str):  # legacy: bare source_hash
        return value, None
    if not isinstance(value, dict):
        return None, None
    lupd = value.get("lupd")
    if isinstance(lupd, str):
        try:
            lupd = date.fromisoformat(lupd)
        except ValueError:
            lupd = None
    return value.get("h"), lupd


def _parse_output(client, batch, meta_by_nct: dict, ingestion_date) -> list[dict]:
    """Download the batch output file and turn each line into trial_eligibility_criteria rows.

    `meta_by_nct` maps custom_id (nct_id) → {"h": source_hash, "lupd": last_update_post_date}
    (or a legacy bare source_hash). Lines for unknown nct_ids or with errors are skipped.
    """
    output_file_id = getattr(batch, "output_file_id", None)
    if not output_file_id:
        logger.warning("Batch %s has no output_file_id (status=%s)", batch.id, batch.status)
        return []

    content = client.files.content(output_file_id)
    text = content.text if hasattr(content, "text") else content.read().decode("utf-8")

    rows: list[dict] = []
    ok = err = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        nct_id = record.get("custom_id")
        source_hash, lupd = _meta(meta_by_nct.get(nct_id))
        if record.get("error") or source_hash is None:
            err += 1
            continue
        body = (record.get("response") or {}).get("body") or {}
        raw = _output_text(body)
        if not raw:
            err += 1
            continue
        try:
            parsed = ExtractedEligibility.model_validate_json(raw)
        except Exception:
            logger.warning("Could not parse eligibility output for %s", nct_id)
            err += 1
            continue
        rows.extend(
            to_db_rows(
                nct_id, parsed.criteria, source_hash=source_hash,
                ingestion_date=ingestion_date, last_update_post_date=lupd,
            )
        )
        ok += 1
    logger.info("Batch %s parsed: %d ok, %d skipped/errored → %d rows", batch.id, ok, err, len(rows))
    return rows


def run_batch_extraction(
    transformed_studies: Iterable[dict],
    ingestion_date: date,
    skip_existing_check: bool = False,
) -> list[dict]:
    """**Blocking** batch extraction (submit → poll → ingest in-process) → criterion rows.
    For tiny test windows only; the production backfill uses the persisted, non-blocking
    submit_jobs + poll_and_ingest. No-ops to [] without an OpenAI key.
    """
    if not settings.openai_api_key:
        logger.info("Batch eligibility skipped: no OpenAI key configured")
        return []

    studies = list(transformed_studies)
    lupd = lupd_map(studies)
    pending = collect_pending(studies, skip_existing_check)
    if not pending:
        return []

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    all_rows: list[dict] = []
    for group, requests in _iter_request_groups(pending):
        batch, _ = _create_batch(client, requests)
        batch = _poll(
            client, batch.id,
            poll_seconds=settings.eligibility_batch_poll_seconds,
            max_wait_seconds=settings.eligibility_batch_max_wait_seconds,
        )
        if batch.status != "completed":
            logger.error("Batch %s ended status=%s — skipping its results", batch.id, batch.status)
            continue
        meta_by_nct = {nct: {"h": h, "lupd": lupd.get(nct)} for nct, (_t, h) in group.items()}
        all_rows.extend(_parse_output(client, batch, meta_by_nct, ingestion_date))

    logger.info("Batch eligibility (blocking): %d trials → %d criterion rows", len(pending), len(all_rows))
    return all_rows


def submit_jobs(
    transformed_studies: Iterable[dict],
    ingestion_date: date,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    run_id: Optional[str] = None,
    skip_existing_check: bool = False,
) -> list[str]:
    """**Non-blocking**: submit OpenAI batch job(s) and persist a tracking row per job
    (status=submitted). Returns the batch ids. Requires pg_database_url — the async path's
    state lives in the DB so poll_and_ingest can resume it. No-ops to [] without a key.
    """
    if not settings.openai_api_key:
        logger.info("Batch submit skipped: no OpenAI key configured")
        return []
    if not settings.pg_database_url:
        logger.error("Batch submit requires pg_database_url to persist job state — skipping")
        return []

    studies = list(transformed_studies)
    lupd = lupd_map(studies)
    pending = collect_pending(studies, skip_existing_check)
    if not pending:
        return []

    from openai import OpenAI
    from src.tasks.load.pg import create_batch_job

    client = OpenAI(api_key=settings.openai_api_key)
    submitted: list[str] = []
    for group, requests in _iter_request_groups(pending):
        batch, input_file_id = _create_batch(client, requests)
        # request_hashes is JSONB: store source_hash + last_update_post_date (ISO, since
        # JSON has no date type). _meta() converts it back at ingest. Carries the re-extract
        # gate hash and the provenance date through the async round-trip.
        request_hashes = {
            nct: {
                "h": h,
                "lupd": d.isoformat() if isinstance(d := lupd.get(nct), date)
                else d if isinstance(d, str)
                else None,
            }
            for nct, (_t, h) in group.items()
        }
        create_batch_job(
            settings.pg_database_url,
            {
                "openai_batch_id": batch.id,
                "input_file_id": input_file_id,
                "status": "submitted",
                "request_count": len(group),
                "from_date": from_date,
                "to_date": to_date,
                "run_id": run_id,
                "request_hashes": request_hashes,
                "ingestion_date": ingestion_date,
                "submitted_at": datetime.now(timezone.utc),
            },
        )
        submitted.append(batch.id)
    logger.info("Submitted %d eligibility batch job(s) for %d trials", len(submitted), len(pending))
    return submitted


def poll_and_ingest() -> dict:
    """Check active batch jobs against OpenAI; ingest completed ones into Postgres (criterion
    rows + per-item eligibility embeddings) and advance their status. Idempotent and
    resumable — safe to run on a cron. Returns a small summary.
    """
    if not settings.pg_database_url:
        logger.error("poll_and_ingest requires pg_database_url — skipping")
        return {"checked": 0, "ingested": 0}
    if not settings.openai_api_key:
        logger.error("poll_and_ingest requires an OpenAI key — skipping")
        return {"checked": 0, "ingested": 0}

    from openai import OpenAI
    from src.tasks.load.pg import (
        get_active_batch_jobs,
        update_batch_job,
        upsert_eligibility_criteria,
        upsert_embeddings,
    )
    from src.tasks.transform.embed import eligibility_item_chunks, get_embedder

    db = settings.pg_database_url
    jobs = get_active_batch_jobs(db)
    client = OpenAI(api_key=settings.openai_api_key)
    checked = ingested = 0
    for job in jobs:
        checked += 1
        batch_id = job["openai_batch_id"]
        batch = client.batches.retrieve(batch_id)
        now = datetime.now(timezone.utc)
        if batch.status == "completed":
            rows = _parse_output(client, batch, job["request_hashes"], job["ingestion_date"])
            if rows:
                # Postgres only — inference reads PG. BQ parity is a documented follow-up.
                upsert_eligibility_criteria(rows, db)
                chunks = eligibility_item_chunks(rows)
                if chunks:
                    upsert_embeddings(get_embedder().embed_chunks(chunks), db)
            update_batch_job(
                db, batch_id, status="ingested",
                output_file_id=getattr(batch, "output_file_id", None),
                last_checked_at=now, completed_at=now, ingested_at=now,
            )
            ingested += 1
            logger.info("Ingested batch %s (%d rows)", batch_id, len(rows))
        elif batch.status in ("failed", "expired", "cancelled"):
            update_batch_job(
                db, batch_id, status=batch.status, last_checked_at=now,
                completed_at=now, error=str(getattr(batch, "errors", None)),
            )
            logger.warning("Batch %s ended status=%s", batch_id, batch.status)
        else:
            logger.info("Batch %s  status=%s", batch_id, batch.status)
            update_batch_job(db, batch_id, status=_map_status(batch.status), last_checked_at=now)
    logger.info("poll_and_ingest: checked=%d ingested=%d", checked, ingested)
    return {"checked": checked, "ingested": ingested}

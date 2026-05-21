"""
Extract task: fetch studies from the clinicalTrials.gov v2 REST API.

Parallelization strategy
------------------------
The API uses cursor-based pagination so sequential pages cannot be
fetched truly in parallel.  Instead we split the requested date range
into N equal-width windows (default 90 days each) and issue one
independent paginated fetch per window.  All windows are submitted as
Dask *delayed* tasks and computed concurrently on a thread pool, giving
us N-way parallelism with minimal overhead.

Each delayed task returns a list of raw study dicts (the JSON
`protocolSection` plus the top-level `nctId`).  The caller collects and
flattens the results.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from dask.base import compute
from dask.delayed import delayed
import requests
from requests.exceptions import HTTPError, RequestException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────────


def _date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Split [start, end] into consecutive chunks of at most *chunk_days* days."""
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


@retry(
    retry=retry_if_exception_type((HTTPError, RequestException)),
    stop=stop_after_attempt(settings.ct_api_max_retries),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
def _fetch_page(
    client: requests.Session,
    date_filter: str,
    page_token: Optional[str],
) -> dict:
    """Fetch a single page from the studies endpoint and return the parsed JSON."""
    params: dict[str, str | int] = {
        "pageSize": settings.ct_api_page_size,
        "query.term": date_filter,
        "filter.overallStatus": settings.ct_api_overall_statuses,
        "sort": "LastUpdatePostDate",
    }
    if page_token:
        params["pageToken"] = page_token

    resp = client.get(f"{settings.ct_api_base_url}/studies", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


# ── Dask delayed worker ────────────────────────────────────────────────────────


@delayed
def _fetch_chunk(start: date, end: date) -> list[dict]:
    """
    Fetch every page of studies whose lastUpdatePostDate falls in
    [start, end].  Returns a flat list of raw study dicts.

    This function is executed by Dask worker threads; each call is fully
    independent so there are no shared-state issues.
    """
    date_filter = f"AREA[LastUpdatePostDate]RANGE[{start.isoformat()},{end.isoformat()}]"
    studies: list[dict] = []
    page_token: Optional[str] = None
    page_num = 0

    with requests.Session() as client:
        while True:
            page_num += 1
            data = _fetch_page(client, date_filter, page_token)

            page_studies = data.get("studies", [])
            studies.extend(page_studies)

            logger.debug(
                "chunk %s→%s | page %d | +%d studies | total so far %d",
                start,
                end,
                page_num,
                len(page_studies),
                len(studies),
            )

            page_token = data.get("nextPageToken")
            if not page_token:
                break

    return studies


# ── Public API (called by the Prefect flow) ────────────────────────────────────


from typing import Iterator


def extract_studies_streaming(
    from_date: date,
    to_date: date,
    parallelism: int | None = None,
) -> Iterator[list[dict]]:
    """
    Yield one date-range chunk's studies at a time.

    Up to *parallelism* chunks are fetched concurrently (Dask thread pool)
    before yielding, so API throughput is preserved while memory is bounded
    to at most *parallelism* × (one chunk's raw studies) at any moment.

    This replaces the old ``extract_studies_parallel`` for full-load runs
    where loading all studies at once would exhaust RAM.
    """
    all_chunks = _date_chunks(from_date, to_date, settings.date_range_chunk_days)
    n_workers = parallelism or settings.dask_n_workers
    logger.info(
        "Streaming %d date-range chunks (%d days each, parallelism=%d) from %s to %s",
        len(all_chunks),
        settings.date_range_chunk_days,
        n_workers,
        from_date,
        to_date,
    )

    for batch_start in range(0, len(all_chunks), n_workers):
        batch = all_chunks[batch_start : batch_start + n_workers]
        delayed_tasks = [_fetch_chunk(start, end) for start, end in batch]
        results: tuple[list[dict], ...] = compute(
            *delayed_tasks,
            scheduler="threads",
            num_workers=len(batch),
        )
        for chunk_result in results:
            logger.debug("Yielding chunk with %d studies", len(chunk_result))
            yield chunk_result

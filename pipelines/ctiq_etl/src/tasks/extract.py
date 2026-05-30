"""
Extract task: fetch studies from the clinicalTrials.gov v2 REST API.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Iterator, Optional
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


def extract_studies_streaming(start: date, end: date) -> Iterator[list[dict]]:
    """
    Fetch every page of studies whose lastUpdatePostDate falls in
    [start, end].  Yields batches of raw study dicts.
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
            if page_num >= settings.ct_api_max_loop:
                page_num = 0
                yield studies
                studies = []
            page_token = data.get("nextPageToken")
            if not page_token:
                if studies:
                    yield studies
                break


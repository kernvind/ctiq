# src/app/modules/trial_search/hydrator.py
from src.app.modules.trial_search.schemas import (
    TrialCard, MatchingChunk, EligibilitySummary, LocationSummary,
)


def to_card(row) -> TrialCard:
    """Convert a hydrated BQ result row into a display-ready TrialCard."""
    return TrialCard(
        nct_id=row.nct_id,
        brief_title=row.brief_title or "(no title)",
        overall_status=row.overall_status or "UNKNOWN",
        phases=tuple(row.phases or ()),
        best_matching_chunk=MatchingChunk(
            field_type=row.best_chunk.field_type,
            chunk_text=_truncate(row.best_chunk.chunk_text, max_chars=250),
            distance=row.best_chunk.distance,
        ),
        eligibility=EligibilitySummary(
            min_age_raw=row.min_age_raw,
            max_age_raw=row.max_age_raw,
            min_age_years=row.min_age_years,
            max_age_years=row.max_age_years,
            sex=row.sex or "ALL",
            accepts_healthy_volunteers=row.healthy_volunteers,
        ),
        locations=LocationSummary(
            total_sites=row.total_sites or 0,
            recruiting_sites=row.recruiting_sites or 0,
            sample_facilities=tuple(row.sample_facilities or ()),
        ),
        top_chunks=row.top_chunks or [],
        lead_sponsor_name=row.lead_sponsor_name or "(unknown sponsor)",
        lead_sponsor_class=row.lead_sponsor_class or "OTHER",
    )


def _truncate(text: str, max_chars: int = 250) -> str:
    if not text or len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0]
    return truncated + "…"
import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ctiq_db import ClinicalTrial, TrialEmbedding, TrialLocation

from src.app.core.config import Settings
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.schemas import (
    Facility,
    MatchingChunk,
    TrialDetail,
    TrialSearchResultRow,
)

logger = logging.getLogger(__name__)

# Sort key for outcome types on the detail page (primary endpoints first).
_OUTCOME_ORDER: dict[str, int] = {"PRIMARY": 0, "SECONDARY": 1}

# How many sample facilities to surface on a search result card.
_SAMPLE_FACILITIES = 5


def _facility_sort_key(loc: TrialLocation) -> tuple:
    # Recruiting sites first, then alphabetical — same intent as the old SQL.
    return (0 if loc.status == "RECRUITING" else 1, loc.country or "", loc.facility or "")


class TrialSearchRepository:
    """Read-side repository for the trial search use case (SQLAlchemy async ORM)."""

    def __init__(self, session: AsyncSession, settings: Settings):
        self.session = session
        self.settings = settings

    async def vector_search(
        self,
        embedding: list[float],
        fields: Sequence[Field],
        top_k: int,
        phase_filter: Optional[tuple[str, ...]] = None,
        statuses: Optional[tuple[str, ...]] = None,
    ) -> list[TrialSearchResultRow]:
        if not embedding:
            raise ValueError("vector_search requires a non-empty embedding")
        if not fields:
            raise ValueError("vector_search requires at least one field type")

        oversample_k = self.settings.vector_search_oversample_factor * top_k
        field_values = [str(f) for f in fields]

        # ── Q1: the only vector query — KNN over embeddings among pre-filtered trials.
        distance = TrialEmbedding.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(
                TrialEmbedding.nct_id,
                TrialEmbedding.field_type,
                TrialEmbedding.chunk_text,
                distance,
            )
            .join(ClinicalTrial, ClinicalTrial.nct_id == TrialEmbedding.nct_id)
            .where(TrialEmbedding.field_type.in_(field_values))
        )
        if statuses:
            stmt = stmt.where(ClinicalTrial.overall_status.in_(list(statuses)))
        if phase_filter:
            # array overlap (&&): the trial's phases intersect the requested phases.
            stmt = stmt.where(ClinicalTrial.phases.op("&&")(list(phase_filter)))
        stmt = stmt.order_by(distance).limit(oversample_k)

        matched = (await self.session.execute(stmt)).all()

        # Group chunks per trial (rows are already distance-sorted, so the first chunk
        # for each trial is its best match). Replaces the per_trial_matches jsonb_agg CTE.
        chunks_by_trial: dict[str, list[MatchingChunk]] = {}
        for row in matched:
            chunks_by_trial.setdefault(row.nct_id, []).append(
                MatchingChunk(
                    field_type=row.field_type,
                    chunk_text=row.chunk_text,
                    distance=row.distance,
                )
            )

        # Best trials first, by best (smallest) distance; then take top_k.
        ranked_ids = sorted(
            chunks_by_trial, key=lambda nid: chunks_by_trial[nid][0].distance
        )[:top_k]
        if not ranked_ids:
            logger.info("vector_search: no matches (top_k=%d)", top_k)
            return []

        # ── Q2 + Q3: metadata + locations for just the winners (indexed by nct_id).
        trials = await self._fetch_trials(ranked_ids)
        locations = await self._fetch_locations(ranked_ids)

        results = [
            self._to_result_row(trials[nid], chunks_by_trial[nid], locations.get(nid, []))
            for nid in ranked_ids
            if nid in trials
        ]
        logger.info("vector_search returned %d rows (top_k=%d)", len(results), top_k)
        return results

    async def _fetch_trials(self, nct_ids: list[str]) -> dict[str, ClinicalTrial]:
        rows = await self.session.scalars(
            select(ClinicalTrial).where(ClinicalTrial.nct_id.in_(nct_ids))
        )
        return {t.nct_id: t for t in rows}

    async def _fetch_locations(self, nct_ids: list[str]) -> dict[str, list[TrialLocation]]:
        rows = await self.session.scalars(
            select(TrialLocation).where(TrialLocation.nct_id.in_(nct_ids))
        )
        grouped: dict[str, list[TrialLocation]] = {}
        for loc in rows:
            grouped.setdefault(loc.nct_id, []).append(loc)
        return grouped

    def _to_result_row(
        self,
        trial: ClinicalTrial,
        chunks: list[MatchingChunk],
        locations: list[TrialLocation],
    ) -> TrialSearchResultRow:
        sample = sorted(locations, key=_facility_sort_key)[:_SAMPLE_FACILITIES]
        return TrialSearchResultRow(
            nct_id=trial.nct_id,
            brief_title=trial.brief_title,
            brief_summary=trial.brief_summary,
            overall_status=trial.overall_status,
            phases=trial.phases or [],
            conditions=trial.conditions or [],
            lead_sponsor_name=trial.lead_sponsor_name,
            lead_sponsor_class=trial.lead_sponsor_class,
            min_age_years=trial.min_age_years,
            max_age_years=trial.max_age_years,
            sex=trial.sex,
            healthy_volunteers=trial.healthy_volunteers,
            best_distance=chunks[0].distance,
            best_chunk=chunks[0],
            top_chunks=chunks[:3],
            total_sites=len(locations),
            recruiting_sites=sum(1 for loc in locations if loc.status == "RECRUITING"),
            sample_facilities=[
                Facility(
                    facility=loc.facility,
                    city=loc.city,
                    state=loc.state,
                    country=loc.country,
                    status=loc.status,
                )
                for loc in sample
            ],
        )

    async def get_trial(self, nct_id: str) -> Optional[TrialDetail]:
        """Fetch one trial's full record (+ child tables) by NCT id via the ORM.

        Search-agnostic (no embeddings / match context), so the same path backs the detail
        page for authed and anonymous callers. Child collections are eager-loaded with
        selectinload (one extra query per relationship) — no lazy loading, which AsyncSession
        forbids.
        """
        stmt = (
            select(ClinicalTrial)
            .where(ClinicalTrial.nct_id == nct_id)
            .options(
                selectinload(ClinicalTrial.locations),
                selectinload(ClinicalTrial.interventions),
                selectinload(ClinicalTrial.outcomes),
                selectinload(ClinicalTrial.arm_groups),
                selectinload(ClinicalTrial.officials),
            )
        )
        trial = (await self.session.execute(stmt)).scalar_one_or_none()
        if trial is None:
            logger.info("get_trial: no trial found for nct_id=%s", nct_id)
            return None

        # Relationship load order isn't guaranteed — sort in place before mapping so the
        # detail view is deterministic (recruiting sites first; primary outcomes first).
        trial.locations.sort(key=_facility_sort_key)
        # outcome_type can be None; normalize to empty string so dict.get() accepts it
        trial.outcomes.sort(key=lambda o: (_OUTCOME_ORDER.get(o.outcome_type or "", 2), o.id))
        trial.interventions.sort(key=lambda i: i.id)
        trial.arm_groups.sort(key=lambda a: a.id)
        trial.officials.sort(key=lambda o: o.id)

        return TrialDetail.model_validate(trial)

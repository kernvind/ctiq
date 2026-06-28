import logging
import time
from typing import Optional

from src.app.infra.embed.embedder import Embedder
from src.app.modules.eligibility_match.evaluator import match_criteria, rank_matches
from src.app.modules.eligibility_match.repository import EligibilityMatchRepository
from src.app.modules.eligibility_match.schemas import (
    MatchedTrial,
    MatchResult,
    PatientMatchRequest,
    PatientProfile,
)
from src.app.modules.trial_search.planning.schemas import Field
from src.app.modules.trial_search.repository import TrialSearchRepository

logger = logging.getLogger(__name__)


class EligibilityMatchService:
    """Stateless patient↔trial eligibility match over structured predicates (ROADMAP step 6).

    Loads a trial's criteria and evaluates them against the supplied profile. The profile is
    never persisted — matching is purely in-request (the PHI gate). Returns None when the
    trial has no extracted criteria yet (Stage A hasn't run for it).
    """

    def __init__(self, repository: EligibilityMatchRepository):
        self.repository = repository

    async def match(self, nct_id: str, profile: PatientProfile) -> Optional[MatchResult]:
        nct_id = nct_id.strip().upper()
        criteria = await self.repository.get_criteria(nct_id)
        if not criteria:
            logger.info("No eligibility criteria for %s — cannot match", nct_id)
            return None
        result = match_criteria(nct_id, criteria, profile)
        logger.info(
            "Match %s: signal=%s pass=%d fail=%d uncertain=%d",
            nct_id, result.signal.value, result.n_pass, result.n_fail, result.n_uncertain,
        )
        return result


class PatientMatchService:
    """Patient-first matching (ROADMAP step 6): given a profile + condition, generate
    candidate trials (semantic search over recruiting trials for the condition), batch-match
    each against the profile, and return them ranked (likely-eligible first). Stateless — the
    profile is never persisted. The matcher is pure logic (no LLM), so batch matching a
    candidate set is cheap.
    """

    def __init__(
        self,
        search_repository: TrialSearchRepository,
        match_repository: EligibilityMatchRepository,
        embedder: Embedder,
    ):
        self.search_repository = search_repository
        self.match_repository = match_repository
        self.embedder = embedder

    async def match_trials(self, request: PatientMatchRequest) -> list[MatchedTrial]:
        condition = request.condition.strip()
        if not condition:
            logger.info("Empty query received; returning no results")
            return []
        logger.info("Query received; condition=%r recruiting_only=%s top_k=%d", condition, request.recruiting_only, request.top_k)

        # Candidate generation: semantic rank over recruiting trials for the condition
        # (reuses the Slice-3 vector search + structured pre-filters).
        t0 = time.perf_counter()
        embedding = self.embedder.embed_query(condition)
        t_embed = time.perf_counter()
        statuses = ("RECRUITING",) if request.recruiting_only else None
        rows = await self.search_repository.vector_search(
            embedding=embedding,
            fields=(Field.SUMMARY, Field.TITLE),
            top_k=request.top_k,
            statuses=statuses,
            conditions=(condition,),
        )
        t_search = time.perf_counter()
        candidates = [
            {
                "nct_id": r.nct_id,
                "brief_title": r.brief_title,
                "overall_status": r.overall_status,
                "phases": r.phases,
                "conditions": r.conditions,
                "lead_sponsor_name": r.lead_sponsor_name,
            }
            for r in rows
        ]
        criteria_by_nct = await self.match_repository.get_criteria_bulk(
            [c["nct_id"] for c in candidates]
        )
        t_criteria = time.perf_counter()
        ranked = rank_matches(candidates, criteria_by_nct, request.profile)
        t_rank = time.perf_counter()
        logger.info(
            "Patient match: condition=%r candidates=%d (eligible=%d possible=%d excluded=%d) "
            "timing_ms embed=%.0f search=%.0f criteria=%.0f rank=%.0f total=%.0f",
            condition, len(ranked),
            sum(m.signal.value == "likely_eligible" for m in ranked),
            sum(m.signal.value == "possible" for m in ranked),
            sum(m.signal.value == "likely_excluded" for m in ranked),
            (t_embed - t0) * 1000,
            (t_search - t_embed) * 1000,
            (t_criteria - t_search) * 1000,
            (t_rank - t_criteria) * 1000,
            (t_rank - t0) * 1000,
        )
        return ranked

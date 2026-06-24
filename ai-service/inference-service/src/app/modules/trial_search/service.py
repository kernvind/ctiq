import logging
from typing import Optional, Sequence

from src.app.modules.trial_search.hydrater import to_card
from src.app.modules.trial_search.repository import TrialSearchRepository
from src.app.modules.trial_search.schemas import TrialCard, TrialDetail
from src.app.infra.embed.embedder import Embedder
from src.app.modules.trial_search.planning.schemas import QueryPlan
from src.app.modules.trial_search.planning.protocol import QueryPlannerProtocol

logger = logging.getLogger(__name__)


class TrialSearchService:
    def __init__(
        self,
        repository: TrialSearchRepository,
        embedder: Embedder,
        query_planner: QueryPlannerProtocol,
    ):
        self.repository = repository
        self.embedder = embedder
        self.query_planner = query_planner

    async def search_trials(self, query: str) -> list[TrialCard]:
        query = query.strip()
        if not query:
            logger.info("Empty query received; returning no results")
            return []

        logger.info("Search request received: query=%r", query)

        # 1. Plan: decide what to search and how (async — the planner may call an LLM)
        plan: QueryPlan = await self.query_planner.plan(query=query)
        logger.info(
            "Query plan: intent=%s, fields=%s, phase_filter=%s, top_k=%d",
            plan.intent.value,
            [f.value for f in plan.fields],
            list(plan.phase_filter) if plan.phase_filter else None,
            plan.top_k,
        )

        # 2. Embed the query
        embedding = self.embedder.embed_query(query)
        logger.debug("Embedded query: dim=%d", len(embedding))

        # 3. Vector search with structured pre-filters
        results = await self.repository.vector_search(
            embedding=embedding,
            fields=plan.fields,                # tuple — repo should accept Sequence
            top_k=plan.top_k,
            phase_filter=plan.phase_filter,
        )
        logger.info(
            "Search complete: query=%r, results=%d",
            query, len(results),
        )
        cards = [to_card(row) for row in results]
        return cards

    async def get_trial(self, nct_id: str) -> Optional[TrialDetail]:
        nct_id = nct_id.strip().upper()
        if not nct_id:
            return None
        logger.info("Trial detail request received: nct_id=%s", nct_id)
        detail = await self.repository.get_trial(nct_id)
        if detail is None:
            logger.info("Trial detail not found: nct_id=%s", nct_id)
        return detail
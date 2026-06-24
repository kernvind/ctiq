"""Builds the query planner the service uses, and the resilience wrappers around it.

Slice-2 wiring: the live search path uses the LLM planner when an OpenAI key is configured
and transparently falls back to the rule-based planner if the LLM call fails (network,
timeout, API error) — so search never breaks on an LLM outage. With no key, it's the
rule-based planner wrapped to the same async interface.
"""

import logging

from src.app.core.config import Settings
from src.app.modules.trial_search.planning.llm_planner import LLMQueryPlanner
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.modules.trial_search.planning.schemas import QueryPlan

logger = logging.getLogger(__name__)


class FallbackQueryPlanner:
    """Try the (async) primary planner; on any error fall back to the (sync) secondary.

    The LLM planner already degrades a *refusal* to a safe DESCRIPTIVE plan internally;
    this layer covers *exceptions* (the LLM being unreachable) so the live path is robust.
    """

    def __init__(self, primary: LLMQueryPlanner, fallback: RuleBasedQueryPlanner):
        self._primary = primary
        self._fallback = fallback

    async def plan(self, query: str) -> QueryPlan:
        try:
            return await self._primary.plan(query)
        except Exception:
            logger.warning(
                "LLM planner failed; falling back to rule-based planner", exc_info=True
            )
            return self._fallback.plan(query)


class SyncPlannerAdapter:
    """Wrap a synchronous planner so the service can `await` one uniform interface."""

    def __init__(self, inner: RuleBasedQueryPlanner):
        self._inner = inner

    async def plan(self, query: str) -> QueryPlan:
        return self._inner.plan(query)


def build_query_planner(settings: Settings):
    """LLM planner (+ rule-based fallback) when an OpenAI key is set; else rule-based."""
    rule_based = RuleBasedQueryPlanner()
    if settings.openai_api_key:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        logger.info(
            "Query planner: LLM (%s) with rule-based fallback", settings.llm_model
        )
        return FallbackQueryPlanner(
            LLMQueryPlanner(client, settings.llm_model), rule_based
        )
    logger.info("Query planner: rule-based (no OpenAI key configured)")
    return SyncPlannerAdapter(rule_based)

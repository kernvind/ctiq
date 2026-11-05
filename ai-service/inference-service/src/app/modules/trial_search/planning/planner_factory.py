"""Builds the query planner the service uses, and the resilience/efficiency wrappers around it.

The live search path uses the LLM planner when an OpenAI key is configured and transparently
falls back to the rule-based planner if the LLM call fails (network, timeout, API error) — so
search never breaks on an LLM outage. With no key, it's the rule-based planner wrapped to the
same async interface.

Two efficiency wrappers keep the highest-volume surface (public search) off the LLM:
  - **FastPathQueryPlanner** routes queries with no structured-filter signal straight to the
    rule-based planner (no LLM call) — for a plain condition/concept query there is nothing for
    the LLM to extract or strip, so the two planners are ~equivalent.
  - **CachingQueryPlanner** memoizes plans by normalized query, so repeated/popular searches
    (the bulk of funnel volume) never re-hit the planner.
"""

import logging
import re
from collections import OrderedDict

from src.app.core.config import Settings
from src.app.infra.observability.metrics import LLM_FALLBACKS, PLANNER_CACHE, PLANNER_ROUTE
from src.app.modules.trial_search.planning.llm_planner import LLMQueryPlanner
from src.app.modules.trial_search.planning.protocol import QueryPlannerProtocol
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.modules.trial_search.planning.schemas import PHASE_PATTERNS_SORTED, QueryPlan

logger = logging.getLogger(__name__)

# Recruitment-status words that imply a status pre-filter the rule-based planner can't extract.
_STATUS_HINTS: tuple[str, ...] = (
    "recruiting", "enrolling", "completed", "terminated",
    "withdrawn", "suspended", "active not recruiting", "not yet",
)
# Cheap proper-noun-ish signals that a lead sponsor / company is named. Imperfect: a bare
# sponsor query with none of these ("pfizer melanoma") still routes to rule-based and loses the
# sponsor filter — an accepted trade to keep the condition-query majority off the LLM.
_SPONSOR_HINTS: tuple[str, ...] = (
    "sponsor", "pipeline", "made by", " by ", "pharma", "therapeutics",
    "biosciences", "biotech", "laboratories", " inc", " ltd", " plc", " gmbh",
)


def needs_llm(query: str) -> bool:
    """True when the query carries a structured-filter signal (phase / status / sponsor) the
    LLM can act on — i.e. when the LLM is worth its latency + cost. A plain condition/concept
    query returns False (nothing to extract or strip), and takes the rule-based fast path."""
    q = query.lower()
    if any(re.search(rf"\b{re.escape(p)}\b", q) for p, _ in PHASE_PATTERNS_SORTED):
        return True
    if any(h in q for h in _STATUS_HINTS):
        return True
    return any(h in q for h in _SPONSOR_HINTS)


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
            LLM_FALLBACKS.inc()
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


class FastPathQueryPlanner:
    """Route queries with no structured-filter signal to the (sync) rule-based planner,
    skipping the LLM. The LLM earns its cost only when there's a phase / status / sponsor to
    extract or filter words to strip; a plain condition query has none, so rule-based is
    ~equivalent at zero latency/cost. Filter-signal queries go to the LLM (+fallback) primary."""

    def __init__(self, primary: QueryPlannerProtocol, simple: RuleBasedQueryPlanner):
        self._primary = primary
        self._simple = simple

    async def plan(self, query: str) -> QueryPlan:
        if needs_llm(query):
            PLANNER_ROUTE.labels("llm").inc()
            return await self._primary.plan(query)
        PLANNER_ROUTE.labels("rule_based").inc()
        return self._simple.plan(query)


class CachingQueryPlanner:
    """Memoize plans by normalized query (bounded LRU). Repeated/popular searches — the bulk
    of public-funnel volume — return a cached plan and never re-hit the planner or its LLM
    call. QueryPlan is a frozen dataclass, so sharing cached instances is safe."""

    def __init__(self, inner: QueryPlannerProtocol, maxsize: int):
        self._inner = inner
        self._maxsize = maxsize
        self._cache: "OrderedDict[str, QueryPlan]" = OrderedDict()

    async def plan(self, query: str) -> QueryPlan:
        key = query.strip().lower()
        cached = self._cache.get(key)
        if cached is not None:
            PLANNER_CACHE.labels("hit").inc()
            self._cache.move_to_end(key)
            return cached
        PLANNER_CACHE.labels("miss").inc()
        # Note: two concurrent misses on the same key may both compute (no lock) — acceptable;
        # the cost is a rare duplicate call, never a corrupt cache (writes are await-free).
        plan = await self._inner.plan(query)
        self._cache[key] = plan
        self._cache.move_to_end(key)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)
        return plan


def build_query_planner(settings: Settings) -> QueryPlannerProtocol:
    """Rule-based planner with no key. With a key: LLM (+rule-based fallback), behind a
    fast-path that skips the LLM for filter-less queries, behind an LRU cache."""
    rule_based = RuleBasedQueryPlanner()
    if not settings.openai_api_key:
        logger.info("Query planner: rule-based (no OpenAI key configured)")
        return SyncPlannerAdapter(rule_based)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    planner: QueryPlannerProtocol = FastPathQueryPlanner(
        FallbackQueryPlanner(LLMQueryPlanner(client, settings.llm_model), rule_based),
        rule_based,
    )
    if settings.query_plan_cache_size > 0:
        planner = CachingQueryPlanner(planner, settings.query_plan_cache_size)
    logger.info(
        "Query planner: LLM (%s) + rule-based fallback, fast-path + cache(size=%d)",
        settings.llm_model, settings.query_plan_cache_size,
    )
    return planner

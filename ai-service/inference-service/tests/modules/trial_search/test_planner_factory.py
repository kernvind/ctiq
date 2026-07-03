import asyncio

from src.app.core.config import Settings
from src.app.modules.trial_search.planning.planner_factory import (
    CachingQueryPlanner,
    FallbackQueryPlanner,
    FastPathQueryPlanner,
    SyncPlannerAdapter,
    build_query_planner,
    needs_llm,
)
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.modules.trial_search.planning.schemas import (
    INTENT_TO_FIELDS,
    Intent,
    QueryPlan,
)


class _RaisingPlanner:
    async def plan(self, query: str) -> QueryPlan:
        raise RuntimeError("LLM unreachable")


class _StubPlanner:
    def __init__(self, plan: QueryPlan):
        self._plan = plan

    async def plan(self, query: str) -> QueryPlan:
        return self._plan


def test_build_uses_rule_based_when_no_key():
    planner = build_query_planner(Settings(openai_api_key=""))

    assert isinstance(planner, SyncPlannerAdapter)
    # Behaves like the rule-based planner (extracts the phase).
    plan = asyncio.run(planner.plan("phase 3 melanoma"))
    assert plan.phase_filter == ("PHASE3",)


class _CountingPlanner:
    """Records how many times plan() is awaited, returning a fixed plan."""

    def __init__(self, plan: QueryPlan):
        self._plan = plan
        self.calls = 0

    async def plan(self, query: str) -> QueryPlan:
        self.calls += 1
        return self._plan


def test_build_wraps_llm_in_fastpath_and_cache_when_key_present():
    planner = build_query_planner(Settings(openai_api_key="sk-test"))
    # Outermost is the cache; it wraps the fast-path, which wraps the LLM(+fallback).
    assert isinstance(planner, CachingQueryPlanner)


def test_build_omits_cache_when_cache_size_zero():
    planner = build_query_planner(
        Settings(openai_api_key="sk-test", query_plan_cache_size=0)
    )
    assert isinstance(planner, FastPathQueryPlanner)


# ── fast-path: only filter-signal queries reach the LLM ───────────────────────
def test_needs_llm_detects_filter_signals():
    assert needs_llm("phase 3 melanoma") is True       # phase
    assert needs_llm("recruiting lung cancer") is True  # status
    assert needs_llm("trials by Pfizer") is True        # sponsor hint
    # Plain condition/concept queries — nothing to extract or strip.
    assert needs_llm("advanced melanoma") is False
    assert needs_llm("GLP-1 obesity") is False


def test_fastpath_skips_primary_for_plain_query():
    primary = _CountingPlanner(
        QueryPlan(intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE])
    )
    planner = FastPathQueryPlanner(primary, RuleBasedQueryPlanner())

    plan = asyncio.run(planner.plan("advanced melanoma"))
    assert primary.calls == 0                 # LLM primary never touched
    assert plan.intent is Intent.DESCRIPTIVE  # came from the rule-based planner


def test_fastpath_uses_primary_for_filter_query():
    expected = QueryPlan(
        intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE],
        status_filter=("RECRUITING",),
    )
    primary = _CountingPlanner(expected)
    planner = FastPathQueryPlanner(primary, RuleBasedQueryPlanner())

    plan = asyncio.run(planner.plan("recruiting melanoma trials"))
    assert primary.calls == 1
    assert plan is expected


# ── cache: repeated queries skip the inner planner ────────────────────────────
def test_cache_memoizes_by_normalized_query():
    inner = _CountingPlanner(
        QueryPlan(intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE])
    )
    planner = CachingQueryPlanner(inner, maxsize=8)

    asyncio.run(planner.plan("melanoma"))
    asyncio.run(planner.plan("  Melanoma "))  # same after normalize → cache hit
    assert inner.calls == 1

    asyncio.run(planner.plan("lung cancer"))  # distinct → recompute
    assert inner.calls == 2


def test_cache_evicts_oldest_beyond_maxsize():
    inner = _CountingPlanner(
        QueryPlan(intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE])
    )
    planner = CachingQueryPlanner(inner, maxsize=1)

    asyncio.run(planner.plan("a"))
    asyncio.run(planner.plan("b"))  # evicts "a"
    asyncio.run(planner.plan("a"))  # recompute (was evicted)
    assert inner.calls == 3


def test_fallback_returns_primary_result_on_success():
    expected = QueryPlan(
        intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE]
    )
    planner = FallbackQueryPlanner(_StubPlanner(expected), RuleBasedQueryPlanner())

    assert asyncio.run(planner.plan("anything")) is expected


def test_fallback_uses_rule_based_when_primary_raises():
    planner = FallbackQueryPlanner(_RaisingPlanner(), RuleBasedQueryPlanner())

    # The LLM "fails", so the rule-based planner classifies this patient self-description.
    plan = asyncio.run(planner.plan("i have stage 3 melanoma, any trials?"))
    assert plan.intent is Intent.PATIENT

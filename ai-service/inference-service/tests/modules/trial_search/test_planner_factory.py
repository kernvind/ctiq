import asyncio

from src.app.core.config import Settings
from src.app.modules.trial_search.planning.planner_factory import (
    FallbackQueryPlanner,
    SyncPlannerAdapter,
    build_query_planner,
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


def test_build_uses_llm_with_fallback_when_key_present():
    planner = build_query_planner(Settings(openai_api_key="sk-test"))

    assert isinstance(planner, FallbackQueryPlanner)


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

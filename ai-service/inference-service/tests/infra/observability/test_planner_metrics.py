import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from prometheus_client import REGISTRY

from src.app.modules.trial_search.planning.llm_planner import LLMQueryPlanner
from src.app.modules.trial_search.planning.llm_schemas import CompiledQuery
from src.app.modules.trial_search.planning.planner_factory import (
    CachingQueryPlanner,
    FallbackQueryPlanner,
    FastPathQueryPlanner,
)
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.modules.trial_search.planning.schemas import QueryPlan, Intent, INTENT_TO_FIELDS


def _v(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


def _compiled() -> CompiledQuery:
    return CompiledQuery(
        intent="descriptive",
        semantic_query="melanoma",
        phases=[],
        statuses=[],
        sponsor=None,
        conditions=[],
    )


def _llm(parse: AsyncMock) -> LLMQueryPlanner:
    return LLMQueryPlanner(SimpleNamespace(responses=SimpleNamespace(parse=parse)), "m-test")


def test_llm_call_records_tokens_latency_and_ok_outcome():
    usage = SimpleNamespace(input_tokens=120, output_tokens=30)
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=_compiled(), usage=usage))
    ok, tin, tout, n = (
        _v("llm_requests_total", model="m-test", outcome="ok"),
        _v("llm_tokens_total", model="m-test", direction="input"),
        _v("llm_tokens_total", model="m-test", direction="output"),
        _v("llm_request_duration_seconds_count", model="m-test"),
    )

    asyncio.run(_llm(parse).plan("phase 3 melanoma"))

    assert _v("llm_requests_total", model="m-test", outcome="ok") - ok == 1
    assert _v("llm_tokens_total", model="m-test", direction="input") - tin == 120
    assert _v("llm_tokens_total", model="m-test", direction="output") - tout == 30
    assert _v("llm_request_duration_seconds_count", model="m-test") - n == 1


def test_llm_refusal_and_missing_usage_are_handled():
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=None))  # no .usage at all
    before = _v("llm_requests_total", model="m-test", outcome="refusal")

    asyncio.run(_llm(parse).plan("phase 3 melanoma"))

    assert _v("llm_requests_total", model="m-test", outcome="refusal") - before == 1


def test_llm_exception_is_counted_and_still_propagates():
    parse = AsyncMock(side_effect=RuntimeError("api down"))
    before = _v("llm_requests_total", model="m-test", outcome="error")

    try:
        asyncio.run(_llm(parse).compile("phase 3 melanoma"))
        raised = False
    except RuntimeError:
        raised = True

    assert raised
    assert _v("llm_requests_total", model="m-test", outcome="error") - before == 1


class _Raises:
    async def plan(self, query):
        raise RuntimeError("down")


def test_fallback_is_counted():
    before = _v("llm_planner_fallbacks_total")
    planner = FallbackQueryPlanner(_Raises(), RuleBasedQueryPlanner())

    asyncio.run(planner.plan("phase 3 melanoma"))

    assert _v("llm_planner_fallbacks_total") - before == 1


def test_fast_path_routes_are_counted():
    rb = RuleBasedQueryPlanner()
    llm_planner = SimpleNamespace(plan=AsyncMock(return_value=rb.plan("x")))
    planner = FastPathQueryPlanner(llm_planner, rb)
    llm0, rb0 = _v("query_planner_route_total", planner="llm"), _v(
        "query_planner_route_total", planner="rule_based"
    )

    asyncio.run(planner.plan("melanoma immunotherapy options"))  # no filter signal
    asyncio.run(planner.plan("phase 3 melanoma"))  # filter signal -> LLM

    assert _v("query_planner_route_total", planner="rule_based") - rb0 == 1
    assert _v("query_planner_route_total", planner="llm") - llm0 == 1


def test_cache_hit_and_miss_are_counted():
    plan = QueryPlan(intent=Intent.DESCRIPTIVE, fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE])
    inner = SimpleNamespace(plan=AsyncMock(return_value=plan))
    planner = CachingQueryPlanner(inner, maxsize=4)
    hit0, miss0 = _v("query_planner_cache_total", result="hit"), _v(
        "query_planner_cache_total", result="miss"
    )

    asyncio.run(planner.plan("same query"))
    asyncio.run(planner.plan("Same Query "))

    assert _v("query_planner_cache_total", result="miss") - miss0 == 1
    assert _v("query_planner_cache_total", result="hit") - hit0 == 1

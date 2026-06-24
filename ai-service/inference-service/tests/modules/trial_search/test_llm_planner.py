import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.app.modules.trial_search.planning.llm_planner import LLMQueryPlanner
from src.app.modules.trial_search.planning.llm_schemas import CompiledQuery
from src.app.modules.trial_search.planning.schemas import Field, Intent


def _compiled(**over) -> CompiledQuery:
    data = dict(
        intent="descriptive",
        semantic_query="melanoma immunotherapy",
        phases=[],
        statuses=[],
        sponsor=None,
        conditions=[],
    )
    data.update(over)
    return CompiledQuery(**data)


def _planner_with(parsed):
    """An LLMQueryPlanner whose injected client returns `parsed` from the Responses API.

    Mirrors `client.responses.parse(...)` returning an object with `.output_parsed`."""
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=parsed))
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    return LLMQueryPlanner(client, model="gpt-5-mini"), parse


def test_maps_descriptive_intent_and_phase():
    planner, parse = _planner_with(_compiled(intent="descriptive", phases=["PHASE3"]))

    plan = asyncio.run(planner.plan("phase 3 melanoma immunotherapy"))

    assert plan.intent is Intent.DESCRIPTIVE
    assert plan.phase_filter == ("PHASE3",)
    assert Field.SUMMARY in plan.fields and Field.TITLE in plan.fields
    assert plan.top_k == 20
    # Called with the configured model and the structured-output format.
    parse.assert_awaited_once()
    kwargs = parse.await_args.kwargs
    assert kwargs["model"] == "gpt-5-mini"
    assert kwargs["text_format"] is CompiledQuery


def test_patient_intent_searches_eligibility():
    planner, _ = _planner_with(_compiled(intent="patient"))

    plan = asyncio.run(planner.plan("i have stage 3 melanoma, any trials?"))

    assert plan.intent is Intent.PATIENT
    assert Field.ELIGIBILITY in plan.fields


def test_competitive_intel_intent_is_activated():
    planner, _ = _planner_with(
        _compiled(intent="competitive_intel", phases=["PHASE2"])
    )

    plan = asyncio.run(planner.plan("what is pfizer doing in oncology"))

    assert plan.intent is Intent.COMPETITIVE_INTEL
    assert plan.phase_filter == ("PHASE2",)


def test_normalizes_and_dedupes_phase_strings():
    planner, _ = _planner_with(
        _compiled(phases=["Phase 3", "garbage", "PHASE_3", "early phase 1"])
    )

    plan = asyncio.run(planner.plan("..."))

    assert plan.phase_filter == ("PHASE3", "EARLY_PHASE1")


def test_empty_phases_means_no_filter():
    planner, _ = _planner_with(_compiled(phases=[]))

    plan = asyncio.run(planner.plan("..."))

    assert plan.phase_filter is None


def test_refusal_falls_back_to_descriptive():
    planner, _ = _planner_with(None)  # parsed is None when the model refuses

    plan = asyncio.run(planner.plan("disallowed request"))

    assert plan.intent is Intent.DESCRIPTIVE
    assert plan.phase_filter is None

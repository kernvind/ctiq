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
    # The fallback plan carries no structured filters.
    assert plan.status_filter is None
    assert plan.sponsor_filter is None
    assert plan.condition_filter is None


def test_normalizes_and_dedupes_status_strings():
    planner, _ = _planner_with(
        _compiled(statuses=["Recruiting", "not yet recruiting", "bogus", "RECRUITING"])
    )

    plan = asyncio.run(planner.plan("..."))

    assert plan.status_filter == ("RECRUITING", "NOT_YET_RECRUITING")


def test_empty_statuses_means_no_filter():
    planner, _ = _planner_with(_compiled(statuses=[]))

    assert asyncio.run(planner.plan("...")).status_filter is None


def test_sponsor_passes_through_trimmed():
    planner, _ = _planner_with(_compiled(sponsor="  Pfizer  "))

    assert asyncio.run(planner.plan("...")).sponsor_filter == "Pfizer"


def test_blank_sponsor_becomes_none():
    planner, _ = _planner_with(_compiled(sponsor="   "))

    assert asyncio.run(planner.plan("...")).sponsor_filter is None


def test_conditions_cleaned_and_deduped():
    planner, _ = _planner_with(
        _compiled(conditions=["melanoma", " melanoma ", "", "lung cancer"])
    )

    assert asyncio.run(planner.plan("...")).condition_filter == ("melanoma", "lung cancer")


def test_semantic_query_passed_through():
    planner, _ = _planner_with(_compiled(semantic_query="GLP-1 obesity"))

    assert asyncio.run(planner.plan("...")).semantic_query == "GLP-1 obesity"


def test_empty_semantic_query_becomes_none():
    # When the model strips everything into filters, the core is empty -> embed raw query.
    planner, _ = _planner_with(_compiled(semantic_query="   "))

    assert asyncio.run(planner.plan("...")).semantic_query is None

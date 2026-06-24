import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.app.modules.trial_search.service import TrialSearchService
from src.app.modules.trial_search.planning.schemas import QueryPlan, Intent, Field


def make_service(rows=None):
    repository = MagicMock()
    repository.vector_search = AsyncMock(return_value=rows or [])
    embedder = MagicMock()
    embedder.embed_query = MagicMock(return_value=[0.1, 0.2])
    planner = MagicMock()
    # The service awaits the planner now (it may call an LLM), so mock it async.
    planner.plan = AsyncMock(
        return_value=QueryPlan(
            intent=Intent.DESCRIPTIVE,
            fields=(Field.SUMMARY,),
            phase_filter=("PHASE3",),
            top_k=20,
        )
    )
    service = TrialSearchService(
        repository=repository, embedder=embedder, query_planner=planner
    )
    return service, repository, embedder, planner


def test_empty_query_returns_empty_without_touching_dependencies():
    service, repo, embedder, planner = make_service()

    result = asyncio.run(service.search_trials("   "))

    assert result == []
    planner.plan.assert_not_called()
    embedder.embed_query.assert_not_called()
    repo.vector_search.assert_not_called()


def test_valid_query_plans_embeds_then_searches_with_plan_params():
    service, repo, embedder, planner = make_service(rows=[])

    result = asyncio.run(service.search_trials("phase 3 melanoma"))

    planner.plan.assert_called_once_with(query="phase 3 melanoma")
    embedder.embed_query.assert_called_once_with("phase 3 melanoma")
    repo.vector_search.assert_called_once()

    kwargs = repo.vector_search.call_args.kwargs
    assert kwargs["embedding"] == [0.1, 0.2]
    assert kwargs["fields"] == (Field.SUMMARY,)
    assert kwargs["top_k"] == 20
    assert kwargs["phase_filter"] == ("PHASE3",)
    assert result == []


def test_get_trial_normalizes_id_and_delegates_to_repository():
    service, repo, _, _ = make_service()
    repo.get_trial = AsyncMock(return_value="sentinel")

    result = asyncio.run(service.get_trial("  nct01234567 "))

    repo.get_trial.assert_called_once_with("NCT01234567")
    assert result == "sentinel"


def test_get_trial_returns_none_when_not_found():
    service, repo, _, _ = make_service()
    repo.get_trial = AsyncMock(return_value=None)

    assert asyncio.run(service.get_trial("NCT99999999")) is None

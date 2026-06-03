from typing import Annotated

from fastapi import Depends, Request
from src.app.modules.trial_search.repository import TrialSearchRepository
from src.app.modules.trial_search.service import TrialSearchService
from src.app.modules.trial_search.planning.rule_based_planner import RuleBasedQueryPlanner
from src.app.infra.bigquery.client import BigQueryClient
from src.app.infra.embed.embedder import Embedder
from src.app.core.config import get_settings, Settings

SettingsDep = Annotated[Settings, Depends(get_settings)]

def get_bq_client(request: Request):
    return request.app.state.bq_client


def get_embedder(request: Request):
    return request.app.state.embedder


def get_query_planner(request: Request):
    return request.app.state.query_planner


def get_trial_search_repository(
    bq: Annotated[BigQueryClient, Depends(get_bq_client)],settings: SettingsDep,
) -> TrialSearchRepository:
    """Stateless wrapper; cheap to construct per request, but easy to mock in tests."""
    return TrialSearchRepository(bq=bq, settings=settings)

def get_trial_search_service(
    repository: Annotated[TrialSearchRepository, Depends(get_trial_search_repository)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    query_planner: Annotated[RuleBasedQueryPlanner, Depends(get_query_planner)],
) -> TrialSearchService:
    return TrialSearchService(
        repository=repository,
        embedder=embedder,
        query_planner=query_planner,
    )
# Type alias for routes to use
TrialSearchServiceDep = Annotated[TrialSearchService, Depends(get_trial_search_service)]
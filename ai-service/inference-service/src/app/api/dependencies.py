from typing import Annotated, AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.app.modules.trial_search.repository import TrialSearchRepository
from src.app.modules.trial_search.service import TrialSearchService
from src.app.modules.trial_search.planning.protocol import QueryPlannerProtocol
from src.app.modules.eligibility_match.repository import EligibilityMatchRepository
from src.app.modules.eligibility_match.service import (
    EligibilityMatchService,
    PatientMatchService,
)
from src.app.infra.embed.embedder import Embedder
from src.app.core.config import get_settings, Settings

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.db_sessionmaker


async def get_session(
    factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncIterator[AsyncSession]:
    async with factory() as session:
        yield session


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_query_planner(request: Request) -> QueryPlannerProtocol:
    return request.app.state.query_planner


def get_trial_search_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: SettingsDep,
) -> TrialSearchRepository:
    return TrialSearchRepository(session=session, settings=settings)


def get_trial_search_service(
    repository: Annotated[TrialSearchRepository, Depends(get_trial_search_repository)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    query_planner: Annotated[QueryPlannerProtocol, Depends(get_query_planner)],
) -> TrialSearchService:
    return TrialSearchService(
        repository=repository,
        embedder=embedder,
        query_planner=query_planner,
    )


TrialSearchServiceDep = Annotated[TrialSearchService, Depends(get_trial_search_service)]


def get_eligibility_match_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EligibilityMatchRepository:
    return EligibilityMatchRepository(session=session)


def get_eligibility_match_service(
    repository: Annotated[EligibilityMatchRepository, Depends(get_eligibility_match_repository)],
) -> EligibilityMatchService:
    return EligibilityMatchService(repository=repository)


EligibilityMatchServiceDep = Annotated[
    EligibilityMatchService, Depends(get_eligibility_match_service)
]


def get_patient_match_service(
    search_repository: Annotated[TrialSearchRepository, Depends(get_trial_search_repository)],
    match_repository: Annotated[EligibilityMatchRepository, Depends(get_eligibility_match_repository)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
) -> PatientMatchService:
    return PatientMatchService(
        search_repository=search_repository,
        match_repository=match_repository,
        embedder=embedder,
    )


PatientMatchServiceDep = Annotated[PatientMatchService, Depends(get_patient_match_service)]

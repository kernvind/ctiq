# src/app/modules/trial_search/routes.py
from typing import Annotated
from fastapi import APIRouter, Query, HTTPException
from src.app.api.dependencies import TrialSearchServiceDep
from src.app.modules.trial_search.schemas import TrialCard

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("/trials", response_model=list[TrialCard])
async def search_trials(
    q: Annotated[str, Query(min_length=10, max_length=500, description="Search query")],
    service: TrialSearchServiceDep,
) -> list[TrialCard]:
    try:
        return await service.search_trials(query=q)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
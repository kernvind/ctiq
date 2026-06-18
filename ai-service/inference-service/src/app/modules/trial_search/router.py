# src/app/modules/trial_search/routes.py
from typing import Annotated
from fastapi import APIRouter, Path, Query, HTTPException
from src.app.api.dependencies import TrialSearchServiceDep
from src.app.modules.trial_search.schemas import TrialCard, TrialDetail

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


@router.get("/trials/{nct_id}", response_model=TrialDetail)
async def get_trial(
    service: TrialSearchServiceDep,
    nct_id: Annotated[
        str,
        Path(pattern=r"^[Nn][Cc][Tt]\d{8}$", description="ClinicalTrials.gov NCT id"),
    ],
) -> TrialDetail:
    detail = await service.get_trial(nct_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Trial {nct_id} not found")
    return detail
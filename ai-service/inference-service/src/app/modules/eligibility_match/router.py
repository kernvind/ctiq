from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from src.app.api.dependencies import EligibilityMatchServiceDep
from src.app.modules.eligibility_match.schemas import MatchResult, PatientProfile

router = APIRouter(prefix="/api/v1/match", tags=["match"])


@router.post("/trials/{nct_id}", response_model=MatchResult)
async def match_trial(
    service: EligibilityMatchServiceDep,
    profile: PatientProfile,
    nct_id: Annotated[
        str,
        Path(pattern=r"^[Nn][Cc][Tt]\d{8}$", description="ClinicalTrials.gov NCT id"),
    ],
) -> MatchResult:
    """Stateless eligibility match of a patient profile against one trial's predicates.

    The profile is evaluated in-request and never stored. 404 when the trial has no
    extracted eligibility criteria yet.
    """
    result = await service.match(nct_id, profile)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No eligibility criteria for {nct_id}")
    return result

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from src.app.api.dependencies import EligibilityMatchServiceDep, PatientMatchServiceDep
from src.app.modules.eligibility_match.schemas import (
    MatchedTrial,
    MatchResult,
    PatientMatchRequest,
    PatientProfile,
    PortfolioMatchRequest,
)

router = APIRouter(prefix="/api/v1/match", tags=["match"])


@router.post("/trials", response_model=list[MatchedTrial])
async def match_trials(
    service: PatientMatchServiceDep,
    request: PatientMatchRequest,
) -> list[MatchedTrial]:
    """Patient-first: rank recruiting trials for a condition by how well the patient profile
    matches their structured eligibility. Drill into POST /match/trials/{nct_id} for the
    per-criterion verdicts. The profile is evaluated in-request and never stored."""
    return await service.match_trials(request)


@router.post("/portfolio", response_model=list[MatchedTrial])
async def match_portfolio(
    service: PatientMatchServiceDep,
    request: PortfolioMatchRequest,
) -> list[MatchedTrial]:
    """Portfolio screening (site-payer wedge): rank an explicit set of trials — a site's
    open-trial portfolio — by how well the patient profile matches their eligibility. No vector
    search. Trials with no extracted criteria come back has_criteria=False. Profile not stored."""
    return await service.screen_portfolio(request.profile, request.nct_ids)


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

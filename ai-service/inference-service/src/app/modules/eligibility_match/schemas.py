"""Schemas for the eligibility matcher (ROADMAP step 6).

Persona-neutral: the same PatientProfile/MatchResult serve the clinician pre-screen and the
patient self-check — only the calling surface and disclaimers differ. Nothing here is
persisted (stateless matching) so no patient health profile is stored (PHI gate).
"""
from enum import StrEnum
from typing import Optional, Union

from pydantic import BaseModel, Field


class Verdict(StrEnum):
    PASS = "pass"                   # the criterion's test is satisfied / not triggered
    FAIL = "fail"                   # inclusion not met, or an exclusion is triggered
    UNCERTAIN = "uncertain"         # evaluable predicate, but the patient datum is missing
    NOT_EVALUATED = "not_evaluated" # no structured predicate (prose) — needs human review


class TrialSignal(StrEnum):
    LIKELY_ELIGIBLE = "likely_eligible"   # every evaluable test passed
    POSSIBLE = "possible"                 # no fails, but some uncertain / nothing evaluable
    LIKELY_EXCLUDED = "likely_excluded"   # at least one evaluable test failed


class PatientProfile(BaseModel):
    """A structured patient snapshot to evaluate against trial predicates. All optional —
    missing fields produce UNCERTAIN verdicts rather than guesses. NEVER persisted."""

    age_years: Optional[float] = None
    sex: Optional[str] = None  # MALE | FEMALE
    ecog: Optional[int] = None
    stage: Optional[str] = None  # e.g. "IV", "IIIA"
    # marker -> value: numeric ("PD-L1": 60) or status string ("EGFR": "wild-type").
    biomarkers: dict[str, Union[str, float]] = Field(default_factory=dict)
    prior_therapies: list[str] = Field(default_factory=list)  # therapy classes received
    treatment_naive: Optional[bool] = None
    labs: dict[str, float] = Field(default_factory=dict)  # analyte -> value
    # therapy/event keyword -> days since it last occurred (e.g. {"chemotherapy": 14}). Feeds
    # washout/temporal evaluation: "no X within N days" needs the elapsed time, not just that
    # X was received. Keys are matched to a criterion's therapy_class by substring (see evaluator).
    washouts: dict[str, int] = Field(default_factory=dict)


class CriterionVerdict(BaseModel):
    """Per-criterion outcome — this list IS the match explanation."""

    criterion_type: str            # inclusion | exclusion
    category: Optional[str]
    text: str                      # verbatim criterion (joins back via chunk_id elsewhere)
    verdict: Verdict
    reason: str                    # human-readable why


class MatchResult(BaseModel):
    nct_id: str
    signal: TrialSignal
    n_pass: int
    n_fail: int
    n_uncertain: int
    n_not_evaluated: int
    verdicts: list[CriterionVerdict]


class MatchedTrial(BaseModel):
    """A candidate trial + its match summary, for the patient-first ranked list (no per-
    criterion verdicts — drill into POST /match/trials/{nct_id} for those)."""

    nct_id: str
    brief_title: Optional[str] = None
    overall_status: Optional[str] = None
    phases: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    lead_sponsor_name: Optional[str] = None
    signal: TrialSignal
    n_pass: int
    n_fail: int
    n_uncertain: int
    n_not_evaluated: int
    # False when the trial has no extracted eligibility yet — signal defaults to POSSIBLE,
    # so the UI can show "not enough structured data" rather than a real "possible".
    has_criteria: bool
    # The FAIL verdicts that drove a likely_excluded signal — the "single blocker(s)" so the UI
    # can say *why* inline ("Excluded: ECOG 2 vs required [0,1]") without a drill-in round-trip.
    # Empty unless the trial failed at least one criterion. Verdict is always FAIL here.
    blockers: list[CriterionVerdict] = Field(default_factory=list)


class PatientMatchRequest(BaseModel):
    """Patient-first request: a profile + the condition to search candidates for."""

    profile: PatientProfile
    condition: str
    top_k: int = 50
    recruiting_only: bool = True


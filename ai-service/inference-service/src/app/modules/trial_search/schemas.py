# src/app/modules/trial_search/schemas.py

from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class MatchingChunk(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_type: str
    chunk_text: str
    distance: float

class Facility(BaseModel):
    model_config = ConfigDict(frozen=True)

    facility: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None

class TrialSearchResultRow(BaseModel):
    nct_id: str
    brief_title: Optional[str] = None
    brief_summary: Optional[str] = None
    overall_status: Optional[str] = None
    phases: list[str] = []
    conditions: list[str] = []
    lead_sponsor_name: Optional[str] = None
    lead_sponsor_class: Optional[str] = None

    # Eligibility
    min_age_years: Optional[float] = None
    max_age_years: Optional[float] = None
    sex: Optional[str] = None
    healthy_volunteers: Optional[bool] = None

    # Match context
    best_distance: float
    best_chunk: MatchingChunk
    top_chunks: list[MatchingChunk]

    # Locations
    total_sites: int = 0
    recruiting_sites: int = 0
    sample_facilities: list[Facility] = []

    model_config = {"from_attributes": True}   # tolerate BQ Row attribute access

class EligibilitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_age_years: Optional[float] = None
    max_age_years: Optional[float] = None
    sex: str = "ALL"
    accepts_healthy_volunteers: Optional[bool] = None
    short_summary: Optional[str] = None


class LocationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_sites: int = 0
    recruiting_sites: int = 0
    sample_facilities: tuple[Facility, ...] = ()
    nearest_facility: Optional[str] = None
    nearest_distance_km: Optional[float] = None


class TrialCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    nct_id: str
    brief_title: str
    overall_status: str
    phases: tuple[str, ...]

    best_matching_chunk: MatchingChunk
    match_explanation: Optional[str] = None
    top_chunks: list[MatchingChunk] = []
    eligibility: EligibilitySummary
    locations: LocationSummary

    lead_sponsor_name: str
    lead_sponsor_class: str


# ── Trial detail (single trial, full record) ────────────────────────────────────
# Backs the detail page. This is the full clinical_trials row + its child tables,
# unranked and search-agnostic (no embeddings / match context) — so the same path
# can serve the authed dashboard and the future public surface.


class ContactInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class Collaborator(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    name: Optional[str] = None
    # The JSONB key is "class" (a Python keyword); read it via alias, emit as
    # `sponsor_class` to keep the outgoing JSON clean.
    sponsor_class: Optional[str] = Field(default=None, alias="class")


class Reference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    citation: Optional[str] = None
    type: Optional[str] = None
    pmid: Optional[str] = None


class TrialLocationDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    facility: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip: Optional[str] = None
    status: Optional[str] = None


class TrialInterventionDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class TrialOutcomeDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome_type: Optional[str] = None
    measure: Optional[str] = None
    description: Optional[str] = None
    time_frame: Optional[str] = None


class TrialArmGroupDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None


class TrialOfficialDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Optional[str] = None
    affiliation: Optional[str] = None
    role: Optional[str] = None


class TrialDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nct_id: str

    # Identification
    brief_title: Optional[str] = None
    official_title: Optional[str] = None
    acronym: Optional[str] = None
    organization: Optional[str] = None

    # Status / dates
    overall_status: Optional[str] = None
    start_date: Optional[date] = None
    completion_date: Optional[date] = None
    primary_completion_date: Optional[date] = None
    last_update_post_date: Optional[date] = None

    # Sponsor
    lead_sponsor_name: Optional[str] = None
    lead_sponsor_class: Optional[str] = None
    collaborators: list[Collaborator] = []

    # Design
    study_type: Optional[str] = None
    phases: list[str] = []
    allocation: Optional[str] = None
    intervention_model: Optional[str] = None
    primary_purpose: Optional[str] = None
    masking: Optional[str] = None
    enrollment_count: Optional[int] = None
    enrollment_type: Optional[str] = None

    # Topic
    conditions: list[str] = []
    keywords: list[str] = []

    # Eligibility
    eligibility_criteria: Optional[str] = None
    min_age_years: Optional[float] = None
    max_age_years: Optional[float] = None
    sex: Optional[str] = None
    std_ages: list[str] = []
    healthy_volunteers: Optional[bool] = None

    # Descriptions
    brief_summary: Optional[str] = None
    detailed_description: Optional[str] = None

    # Contacts / references
    central_contacts: list[ContactInfo] = []
    references: list[Reference] = []

    # Child collections
    locations: list[TrialLocationDetail] = []
    interventions: list[TrialInterventionDetail] = []
    outcomes: list[TrialOutcomeDetail] = []
    arm_groups: list[TrialArmGroupDetail] = []
    officials: list[TrialOfficialDetail] = []

    @field_validator(
        "collaborators", "phases", "conditions", "keywords", "std_ages",
        "central_contacts", "references", "locations", "interventions",
        "outcomes", "arm_groups", "officials",
        mode="before",
    )
    @classmethod
    def _none_to_empty_list(cls, v):
        # Nullable array/JSONB columns come back as NULL -> None; the `= []` default only
        # applies when the key is absent, so coerce None to an empty list here.
        return [] if v is None else v
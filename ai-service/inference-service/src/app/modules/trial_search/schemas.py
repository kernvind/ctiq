# src/app/modules/trial_search/schemas.py

from typing import Optional
from pydantic import BaseModel, ConfigDict


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
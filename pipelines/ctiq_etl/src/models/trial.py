"""
Pydantic models that mirror the BigQuery clinical_trials_gov_stg schema.

Every field name intentionally matches the BQ column name so that
model.to_bq_row() can be passed directly to the BigQuery JSON load API
without any further key remapping.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Reference(BaseModel):
    """Maps to ARRAY<STRUCT<citation STRING, type STRING, pmid INT64>>."""

    citation: Optional[str] = None
    type: Optional[str] = None
    pmid: Optional[int] = None


class Outcome(BaseModel):
    """Maps to ARRAY<STRUCT<timeFrame STRING, description STRING, measure STRING>>.

    Used for both primary and secondary outcomes.
    """

    timeFrame: Optional[str] = None
    description: Optional[str] = None
    measure: Optional[str] = None


class Intervention(BaseModel):
    """Maps to ARRAY<STRUCT<description STRING, type STRING, name STRING>>."""

    description: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None


class ClinicalTrial(BaseModel):
    """
    Flat representation of a single study, column-for-column with
    data-eng-470620.healthcare_ai.clinical_trials_gov_stg.
    """

    # ── Required (NOT NULL in BQ) ─────────────────────────────────────────────
    nct_id: str
    lastUpdatePostDate: date
    startDate: date

    # ── Scalars ───────────────────────────────────────────────────────────────
    completionDate: Optional[date] = None
    primaryCompletionDate: Optional[date] = None
    eligibilityCriteria_minimumAge: Optional[str] = None
    organization: Optional[str] = None
    overallStatus: Optional[str] = None
    designModule_enrollmentInfo_count: Optional[int] = None
    designModule_designInfo_maskingInfo_masking: Optional[str] = None
    designModule_designInfo_interventionModel: Optional[str] = None
    designModule_designInfo_primaryPurpose: Optional[str] = None
    eligibilityCriteria: Optional[str] = None
    designModule_designInfo_allocation: Optional[str] = None
    officialTitle: Optional[str] = None
    eligibilityCriteria_healthyVolunteers: Optional[bool] = None
    designModule_studyType: Optional[str] = None
    leadSponsorName: Optional[str] = None
    eligibilityCriteria_sex: Optional[str] = None
    detailedDescription: Optional[str] = None
    investigatorFullName: Optional[str] = None

    # ── Arrays of scalars ─────────────────────────────────────────────────────
    eligibilityCriteria_stdAges: list[str] = Field(default_factory=list)
    conditionsModule: list[str] = Field(default_factory=list)
    leadSponsorCollaborators: list[str] = Field(default_factory=list)

    # ── Arrays of structs ─────────────────────────────────────────────────────
    outcomesModule_primaryOutcomes: list[Outcome] = Field(default_factory=list)
    armsInterventionsModule_interventions: list[Intervention] = Field(default_factory=list)
    outcomesModule_secondaryOutcomes: list[Outcome] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)

    def to_bq_row(self) -> dict:
        """
        Return a dict ready for BigQuery's JSON load API.
        Dates are serialized as ISO-8601 strings ("YYYY-MM-DD").
        Nested structs are kept as dicts; None values are preserved so
        BQ accepts nullable fields.
        """
        row = self.model_dump()

        for field in ("lastUpdatePostDate", "startDate", "completionDate", "primaryCompletionDate"):
            val = row[field]
            if val is not None and hasattr(val, "isoformat"):
                row[field] = val.isoformat()

        return row

from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, BigInteger, Boolean, Date, DateTime, Float, Integer, MetaData, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# All trial-domain tables live in the dedicated `trials` schema, separate from the
# user/auth domain (owned by api-core's Prisma schema `app`). See the two-ORM domain
# split in the ctiq-product-engineering skill. Setting the schema on the shared
# MetaData makes every model below resolve to `trials.<table>` automatically.
TRIALS_SCHEMA = "trials"


class Base(DeclarativeBase):
    metadata = MetaData(schema=TRIALS_SCHEMA)


class ClinicalTrial(Base):
    __tablename__ = "clinical_trials"

    nct_id: Mapped[str] = mapped_column(String, primary_key=True)

    # Identification
    brief_title: Mapped[Optional[str]] = mapped_column(Text)
    official_title: Mapped[Optional[str]] = mapped_column(Text)
    acronym: Mapped[Optional[str]] = mapped_column(String)
    organization: Mapped[Optional[str]] = mapped_column(String)
    organization_class: Mapped[Optional[str]] = mapped_column(String)
    secondary_ids: Mapped[Optional[list]] = mapped_column(JSONB)  # [{id, type, link}]

    # Status / Dates
    overall_status: Mapped[Optional[str]] = mapped_column(String)
    has_results: Mapped[Optional[bool]] = mapped_column(Boolean)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    start_date_type: Mapped[Optional[str]] = mapped_column(String)
    completion_date: Mapped[Optional[date]] = mapped_column(Date)
    primary_completion_date: Mapped[Optional[date]] = mapped_column(Date)
    study_first_post_date: Mapped[Optional[date]] = mapped_column(Date)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Sponsor
    lead_sponsor_name: Mapped[Optional[str]] = mapped_column(String)
    lead_sponsor_class: Mapped[Optional[str]] = mapped_column(String)
    collaborators: Mapped[Optional[list]] = mapped_column(JSONB)  # [{name, class}]
    responsible_party_investigator: Mapped[Optional[str]] = mapped_column(String)
    responsible_party_affiliation: Mapped[Optional[str]] = mapped_column(String)
    responsible_party_type: Mapped[Optional[str]] = mapped_column(String)

    # Design
    study_type: Mapped[Optional[str]] = mapped_column(String)
    phases: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    allocation: Mapped[Optional[str]] = mapped_column(String)
    intervention_model: Mapped[Optional[str]] = mapped_column(String)
    primary_purpose: Mapped[Optional[str]] = mapped_column(String)
    masking: Mapped[Optional[str]] = mapped_column(String)
    enrollment_count: Mapped[Optional[int]] = mapped_column(BigInteger)
    enrollment_type: Mapped[Optional[str]] = mapped_column(String)

    # Conditions / Keywords
    conditions: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    keywords: Mapped[Optional[list]] = mapped_column(ARRAY(Text))

    # Eligibility
    eligibility_criteria: Mapped[Optional[str]] = mapped_column(Text)
    min_age_raw: Mapped[Optional[str]] = mapped_column(String)
    max_age_raw: Mapped[Optional[str]] = mapped_column(String)
    min_age_years: Mapped[Optional[float]] = mapped_column(Float)
    max_age_years: Mapped[Optional[float]] = mapped_column(Float)
    sex: Mapped[Optional[str]] = mapped_column(String)
    std_ages: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    healthy_volunteers: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Description
    brief_summary: Mapped[Optional[str]] = mapped_column(Text)
    detailed_description: Mapped[Optional[str]] = mapped_column(Text)

    # Oversight
    is_fda_regulated_drug: Mapped[Optional[bool]] = mapped_column(Boolean)
    is_fda_regulated_device: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_dmc: Mapped[Optional[bool]] = mapped_column(Boolean)

    # Contacts / references
    central_contacts: Mapped[Optional[list]] = mapped_column(JSONB)  # [{name, role, phone, email}]
    references: Mapped[Optional[list]] = mapped_column(JSONB)        # [{citation, type, pmid}]


class TrialLocation(Base):
    __tablename__ = "trial_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    facility: Mapped[Optional[str]] = mapped_column(String)
    city: Mapped[Optional[str]] = mapped_column(String)
    state: Mapped[Optional[str]] = mapped_column(String)
    country: Mapped[Optional[str]] = mapped_column(String)
    zip: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[Optional[str]] = mapped_column(String)
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    contacts: Mapped[Optional[list]] = mapped_column(JSONB)  # [{name, role, phone, email}]
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialMeshTerm(Base):
    __tablename__ = "trial_mesh_terms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    mesh_id: Mapped[Optional[str]] = mapped_column(String)
    mesh_term: Mapped[Optional[str]] = mapped_column(String)
    browse_type: Mapped[Optional[str]] = mapped_column(String)
    is_ancestor: Mapped[Optional[bool]] = mapped_column(Boolean)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialArmGroup(Base):
    __tablename__ = "trial_arm_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    label: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    intervention_names: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialIntervention(Base):
    __tablename__ = "trial_interventions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    type: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    other_names: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    arm_group_labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialOutcome(Base):
    __tablename__ = "trial_outcomes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    outcome_type: Mapped[Optional[str]] = mapped_column(String)
    measure: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    time_frame: Mapped[Optional[str]] = mapped_column(String)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialOfficial(Base):
    __tablename__ = "trial_officials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String)
    affiliation: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[Optional[str]] = mapped_column(String)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)


class TrialEmbedding(Base):
    __tablename__ = "trial_embeddings"

    nct_id: Mapped[str] = mapped_column(String, primary_key=True)
    field_type: Mapped[str] = mapped_column(String, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768))
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

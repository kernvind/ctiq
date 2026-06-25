from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# All trial-domain tables live in the dedicated `trials` schema, separate from the
# user/auth domain (owned by api-core's Prisma schema `app`). See the two-ORM domain
# split in the ctiq-product-engineering skill. Setting the schema on the shared
# MetaData makes every model below resolve to `trials.<table>` automatically.
TRIALS_SCHEMA = "trials"

# Child tables reference the parent by nct_id. Centralize the FK target so all children
# stay consistent (schema-qualified because the MetaData carries a schema).
_TRIAL_FK = f"{TRIALS_SCHEMA}.clinical_trials.nct_id"


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

    # ── Relationships ───────────────────────────────────────────────────────────
    # Child collections, keyed on nct_id. get_trial loads these with selectinload.
    # delete-orphan + passive_deletes pairs with the children's ON DELETE CASCADE FK.
    locations: Mapped[list["TrialLocation"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    mesh_terms: Mapped[list["TrialMeshTerm"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    arm_groups: Mapped[list["TrialArmGroup"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    interventions: Mapped[list["TrialIntervention"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    outcomes: Mapped[list["TrialOutcome"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    officials: Mapped[list["TrialOfficial"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    eligibility_criteria_items: Mapped[list["TrialEligibilityCriterion"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )
    embeddings: Mapped[list["TrialEmbedding"]] = relationship(
        back_populates="trial", cascade="all, delete-orphan", passive_deletes=True
    )


class TrialLocation(Base):
    __tablename__ = "trial_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
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

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="locations")


class TrialMeshTerm(Base):
    __tablename__ = "trial_mesh_terms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    mesh_id: Mapped[Optional[str]] = mapped_column(String)
    mesh_term: Mapped[Optional[str]] = mapped_column(String)
    browse_type: Mapped[Optional[str]] = mapped_column(String)
    is_ancestor: Mapped[Optional[bool]] = mapped_column(Boolean)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="mesh_terms")


class TrialArmGroup(Base):
    __tablename__ = "trial_arm_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[Optional[str]] = mapped_column(String)
    type: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    intervention_names: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="arm_groups")


class TrialIntervention(Base):
    __tablename__ = "trial_interventions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text)
    other_names: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    arm_group_labels: Mapped[Optional[list]] = mapped_column(ARRAY(Text))
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="interventions")


class TrialOutcome(Base):
    __tablename__ = "trial_outcomes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    outcome_type: Mapped[Optional[str]] = mapped_column(String)
    measure: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    time_frame: Mapped[Optional[str]] = mapped_column(String)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="outcomes")


class TrialOfficial(Base):
    __tablename__ = "trial_officials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[Optional[str]] = mapped_column(String)
    affiliation: Mapped[Optional[str]] = mapped_column(String)
    role: Mapped[Optional[str]] = mapped_column(String)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="officials")


class TrialEligibilityCriterion(Base):
    """One atomic eligibility assertion, extracted from the trial's free-text
    `eligibility_criteria` blob (Asset 1 — structured eligibility; see docs/ROADMAP.md
    step 3).

    The unit is an *atomic assertion*, not a source bullet: a single CT.gov bullet often
    bundles several (diagnosis + stage + prior-therapy), so one bullet can yield several
    rows — `source_bullet_index` traces each back. Stage A populates text + category +
    classification; `predicate` (Stage B) is the normalized, machine-comparable form and
    is filled in later, category by category, so it stays nullable.
    """

    __tablename__ = "trial_eligibility_criteria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    # "inclusion" | "exclusion".
    criterion_type: Mapped[str] = mapped_column(String, nullable=False)
    # Verbatim text of the single assertion.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Taxonomy bucket: diagnosis / disease_stage / biomarker / prior_therapy /
    # performance_status / demographic / lab_value / disease_assessment / comorbidity /
    # concomitant_med / reproductive / consent_logistics / other.
    category: Mapped[Optional[str]] = mapped_column(String)
    # Free-text refinement — names the `other` bucket, or adds detail within a category.
    subtype: Mapped[Optional[str]] = mapped_column(String)
    # Normalized, machine-comparable form (Stage B). Null until normalized for this category.
    predicate: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Extractor self-reported confidence in [0, 1]; low values feed the "uncertain" bucket.
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    # False for boilerplate ("Other protocol-defined criteria apply") — never a real filter.
    is_actionable: Mapped[Optional[bool]] = mapped_column(Boolean)
    # Index of the source bullet this assertion was split from (compound-bullet trace).
    source_bullet_index: Mapped[Optional[int]] = mapped_column(Integer)
    # SHA-256 of the source eligibility blob — skip re-extraction when it's unchanged.
    source_hash: Mapped[Optional[str]] = mapped_column(String)
    # Stable ordering for display (mirrors source order).
    display_order: Mapped[Optional[int]] = mapped_column(Integer)
    ingestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_update_post_date: Mapped[Optional[date]] = mapped_column(Date)

    trial: Mapped["ClinicalTrial"] = relationship(
        back_populates="eligibility_criteria_items"
    )


class TrialEmbedding(Base):
    __tablename__ = "trial_embeddings"

    # HNSW index for fast cosine-distance (<=>) nearest-neighbour search — the embedding
    # column is queried on every trial search. vector_cosine_ops matches the `<=>` operator.
    __table_args__ = (
        Index(
            "ix_trial_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    nct_id: Mapped[str] = mapped_column(
        ForeignKey(_TRIAL_FK, ondelete="CASCADE"), primary_key=True
    )
    field_type: Mapped[str] = mapped_column(String, primary_key=True)
    chunk_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(String, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(Vector(768))
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trial: Mapped["ClinicalTrial"] = relationship(back_populates="embeddings")

"""Initial schema: all clinical trials tables with pgvector.

Revision ID: 0001
Revises:
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "clinical_trials",
        sa.Column("nct_id", sa.String(), nullable=False),
        # Identification
        sa.Column("brief_title", sa.Text(), nullable=True),
        sa.Column("official_title", sa.Text(), nullable=True),
        sa.Column("acronym", sa.String(), nullable=True),
        sa.Column("organization", sa.String(), nullable=True),
        sa.Column("organization_class", sa.String(), nullable=True),
        sa.Column("secondary_ids", postgresql.JSONB(), nullable=True),
        # Status / Dates
        sa.Column("overall_status", sa.String(), nullable=True),
        sa.Column("has_results", sa.Boolean(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("start_date_type", sa.String(), nullable=True),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("primary_completion_date", sa.Date(), nullable=True),
        sa.Column("study_first_post_date", sa.Date(), nullable=True),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        # Sponsor
        sa.Column("lead_sponsor_name", sa.String(), nullable=True),
        sa.Column("lead_sponsor_class", sa.String(), nullable=True),
        sa.Column("collaborators", postgresql.JSONB(), nullable=True),
        sa.Column("responsible_party_investigator", sa.String(), nullable=True),
        sa.Column("responsible_party_affiliation", sa.String(), nullable=True),
        sa.Column("responsible_party_type", sa.String(), nullable=True),
        # Design
        sa.Column("study_type", sa.String(), nullable=True),
        sa.Column("phases", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("allocation", sa.String(), nullable=True),
        sa.Column("intervention_model", sa.String(), nullable=True),
        sa.Column("primary_purpose", sa.String(), nullable=True),
        sa.Column("masking", sa.String(), nullable=True),
        sa.Column("enrollment_count", sa.BigInteger(), nullable=True),
        sa.Column("enrollment_type", sa.String(), nullable=True),
        # Conditions / Keywords
        sa.Column("conditions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        # Eligibility
        sa.Column("eligibility_criteria", sa.Text(), nullable=True),
        sa.Column("min_age_raw", sa.String(), nullable=True),
        sa.Column("max_age_raw", sa.String(), nullable=True),
        sa.Column("min_age_years", sa.Float(), nullable=True),
        sa.Column("max_age_years", sa.Float(), nullable=True),
        sa.Column("sex", sa.String(), nullable=True),
        sa.Column("std_ages", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("healthy_volunteers", sa.Boolean(), nullable=True),
        # Description
        sa.Column("brief_summary", sa.Text(), nullable=True),
        sa.Column("detailed_description", sa.Text(), nullable=True),
        # Oversight
        sa.Column("is_fda_regulated_drug", sa.Boolean(), nullable=True),
        sa.Column("is_fda_regulated_device", sa.Boolean(), nullable=True),
        sa.Column("has_dmc", sa.Boolean(), nullable=True),
        # Contacts / references
        sa.Column("central_contacts", postgresql.JSONB(), nullable=True),
        sa.Column("references", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("nct_id"),
    )
    op.create_index("ix_clinical_trials_overall_status", "clinical_trials", ["overall_status"])
    op.create_index("ix_clinical_trials_last_update_post_date", "clinical_trials", ["last_update_post_date"])

    op.create_table(
        "trial_locations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("facility", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("zip", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("contacts", postgresql.JSONB(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_locations_nct_id", "trial_locations", ["nct_id"])

    op.create_table(
        "trial_mesh_terms",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("mesh_id", sa.String(), nullable=True),
        sa.Column("mesh_term", sa.String(), nullable=True),
        sa.Column("browse_type", sa.String(), nullable=True),
        sa.Column("is_ancestor", sa.Boolean(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_mesh_terms_nct_id", "trial_mesh_terms", ["nct_id"])

    op.create_table(
        "trial_arm_groups",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("intervention_names", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_arm_groups_nct_id", "trial_arm_groups", ["nct_id"])

    op.create_table(
        "trial_interventions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("other_names", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("arm_group_labels", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_interventions_nct_id", "trial_interventions", ["nct_id"])

    op.create_table(
        "trial_outcomes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("outcome_type", sa.String(), nullable=True),
        sa.Column("measure", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("time_frame", sa.String(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_outcomes_nct_id", "trial_outcomes", ["nct_id"])

    op.create_table(
        "trial_officials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("affiliation", sa.String(), nullable=True),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trial_officials_nct_id", "trial_officials", ["nct_id"])

    op.create_table(
        "trial_embeddings",
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("field_type", sa.String(), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("nct_id", "field_type", "chunk_id"),
    )
    op.create_index("ix_trial_embeddings_nct_id", "trial_embeddings", ["nct_id"])


def downgrade() -> None:
    op.drop_table("trial_embeddings")
    op.drop_table("trial_officials")
    op.drop_table("trial_outcomes")
    op.drop_table("trial_interventions")
    op.drop_table("trial_arm_groups")
    op.drop_table("trial_mesh_terms")
    op.drop_table("trial_locations")
    op.drop_table("clinical_trials")
    op.execute("DROP EXTENSION IF EXISTS vector")

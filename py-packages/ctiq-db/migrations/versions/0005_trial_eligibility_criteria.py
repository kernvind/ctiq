"""Add trial_eligibility_criteria: structured, per-criterion eligibility (Asset 1).

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-24

Backs the structured-eligibility flagship (docs/ROADMAP.md step 3). Each row is one atomic
eligibility assertion split out of clinical_trials.eligibility_criteria by the ETL LLM
extractor. Stage A fills text + category + classification; `predicate` (Stage B) is the
normalized machine-comparable form and stays nullable until normalized per category.

Lives in the `trials` schema, child of clinical_trials by nct_id (ON DELETE CASCADE),
matching every other trial child table — no cross-ORM FK to the user/auth domain.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "trials"
TABLE = "trial_eligibility_criteria"
NCT_INDEX = "ix_trial_eligibility_criteria_nct_id"
FK_NAME = "fk_trial_eligibility_criteria_nct_id"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nct_id", sa.String(), nullable=False),
        sa.Column("criterion_type", sa.String(), nullable=False),  # inclusion | exclusion
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("subtype", sa.String(), nullable=True),
        sa.Column("predicate", postgresql.JSONB(), nullable=True),  # Stage B
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("is_actionable", sa.Boolean(), nullable=True),
        sa.Column("source_bullet_index", sa.Integer(), nullable=True),
        sa.Column("source_hash", sa.String(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=False),
        sa.Column("last_update_post_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(NCT_INDEX, TABLE, ["nct_id"], schema=SCHEMA)
    op.create_foreign_key(
        FK_NAME,
        source_table=TABLE,
        referent_table="clinical_trials",
        local_cols=["nct_id"],
        remote_cols=["nct_id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, TABLE, schema=SCHEMA, type_="foreignkey")
    op.drop_index(NCT_INDEX, table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)

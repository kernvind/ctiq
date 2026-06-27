"""Add eligibility_batch_jobs: async OpenAI Batch job tracking (Stage A backfill).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-24

Operational state for the async eligibility batch path: submit persists a row, a separate
poll step advances status and ingests results. Standalone tracking table in the `trials`
schema — no nct_id FK, not part of the BQ/parquet pipeline.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "trials"
TABLE = "eligibility_batch_jobs"
IDX = "ix_eligibility_batch_jobs_openai_batch_id"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("openai_batch_id", sa.String(), nullable=False),
        sa.Column("input_file_id", sa.String(), nullable=True),
        sa.Column("output_file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=True),
        sa.Column("from_date", sa.Date(), nullable=True),
        sa.Column("to_date", sa.Date(), nullable=True),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("request_hashes", postgresql.JSONB(), nullable=True),
        sa.Column("ingestion_date", sa.Date(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("openai_batch_id", name="uq_eligibility_batch_jobs_openai_batch_id"),
        schema=SCHEMA,
    )
    op.create_index(IDX, TABLE, ["openai_batch_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index(IDX, table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)

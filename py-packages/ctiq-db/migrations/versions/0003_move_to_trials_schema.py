"""Move all trial-domain tables from public into the dedicated `trials` schema.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-16

Part of the two-ORM domain split: the clinical-trial domain (this package, used by
inference-service and ctiq_etl) lives in schema `trials`, while the user/auth domain
(api-core's Prisma schema) lives in `app`. `ALTER TABLE ... SET SCHEMA` is a
metadata-only operation in PostgreSQL — it preserves all rows, indexes, primary keys,
and the pgvector column; no data is rewritten.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "trials"

# All tables owned by this package (see ctiq_db.models).
_TABLES = [
    "clinical_trials",
    "trial_locations",
    "trial_mesh_terms",
    "trial_arm_groups",
    "trial_interventions",
    "trial_outcomes",
    "trial_officials",
    "trial_embeddings",
]


def upgrade() -> None:
    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
    for table in _TABLES:
        op.execute(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA "{SCHEMA}"')


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'ALTER TABLE IF EXISTS "{SCHEMA}"."{table}" SET SCHEMA public')
    # Leave the (now empty) schema in place; dropping it is intentionally manual.

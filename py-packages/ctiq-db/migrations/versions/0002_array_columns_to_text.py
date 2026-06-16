"""Change array columns from character varying[] to text[].

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Text

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs that need varchar[] -> text[].
# In PostgreSQL this is a metadata-only change — no row rewriting.
_ARRAY_COLS = [
    ("clinical_trials", "phases"),
    ("clinical_trials", "conditions"),
    ("clinical_trials", "keywords"),
    ("clinical_trials", "std_ages"),
    ("trial_arm_groups", "intervention_names"),
    ("trial_interventions", "other_names"),
    ("trial_interventions", "arm_group_labels"),
]


def upgrade() -> None:
    for table, col in _ARRAY_COLS:
        op.alter_column(
            table,
            col,
            type_=ARRAY(Text),
            postgresql_using=f"{col}::text[]",
        )


def downgrade() -> None:
    from sqlalchemy import String
    for table, col in _ARRAY_COLS:
        op.alter_column(
            table,
            col,
            type_=ARRAY(String),
            postgresql_using=f"{col}::character varying[]",
        )

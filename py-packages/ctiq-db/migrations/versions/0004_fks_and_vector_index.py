"""Add child→parent foreign keys (on nct_id) and an HNSW index on trial embeddings.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-18

Two changes that let inference-service move from raw asyncpg SQL to the SQLAlchemy ORM:

1. FKs from every child table's nct_id to clinical_trials.nct_id (ON DELETE CASCADE).
   This makes the ORM relationships real at the DB level and enforces referential
   integrity. NOTE: adding the FK fails if orphan child rows exist — that's intentional;
   a failure means the trials data has children pointing at missing parents and should
   be investigated rather than silently ignored.

2. An HNSW index on trial_embeddings.embedding using vector_cosine_ops, matching the
   `<=>` cosine-distance operator used by trial search. The embedding column is scanned
   on every search; without an ANN index that's an exact sequential scan.

   The index build reads the whole table and can be memory/time-heavy on a large
   embeddings table. If this is disruptive in a live environment, build it out-of-band
   with `CREATE INDEX CONCURRENTLY` instead (cannot run inside Alembic's transaction).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "trials"
PARENT = "clinical_trials"

# child table -> FK constraint name
_CHILDREN = {
    "trial_locations": "fk_trial_locations_nct_id",
    "trial_mesh_terms": "fk_trial_mesh_terms_nct_id",
    "trial_arm_groups": "fk_trial_arm_groups_nct_id",
    "trial_interventions": "fk_trial_interventions_nct_id",
    "trial_outcomes": "fk_trial_outcomes_nct_id",
    "trial_officials": "fk_trial_officials_nct_id",
    "trial_embeddings": "fk_trial_embeddings_nct_id",
}

HNSW_INDEX = "ix_trial_embeddings_embedding_hnsw"


def upgrade() -> None:
    for table, fk_name in _CHILDREN.items():
        op.create_foreign_key(
            fk_name,
            source_table=table,
            referent_table=PARENT,
            local_cols=["nct_id"],
            remote_cols=["nct_id"],
            source_schema=SCHEMA,
            referent_schema=SCHEMA,
            ondelete="CASCADE",
        )

    op.create_index(
        HNSW_INDEX,
        "trial_embeddings",
        ["embedding"],
        schema=SCHEMA,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index(HNSW_INDEX, table_name="trial_embeddings", schema=SCHEMA)
    for table, fk_name in _CHILDREN.items():
        op.drop_constraint(fk_name, table, schema=SCHEMA, type_="foreignkey")

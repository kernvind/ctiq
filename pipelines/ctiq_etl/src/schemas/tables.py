# src/clinical_trials/schemas/tables.py
from dataclasses import dataclass
from typing import Literal

MergeStrategy = Literal["upsert_on_nct_id", "replace_by_nct_id"]

@dataclass(frozen=True)
class TableConfig:
    gcs_subdir: str
    curated_table: str
    strategy: MergeStrategy

TABLE_CONFIGS: tuple[TableConfig, ...] = (
    TableConfig("trial",         "clinical_trials_gov",            "upsert_on_nct_id"),
    TableConfig("locations",     "clinical_trials_locations",      "replace_by_nct_id"),
    TableConfig("mesh_terms",    "clinical_trials_mesh_terms",     "replace_by_nct_id"),
    TableConfig("arm_groups",    "clinical_trials_arm_groups",     "replace_by_nct_id"),
    TableConfig("interventions", "clinical_trials_interventions",  "replace_by_nct_id"),
    TableConfig("outcomes",      "clinical_trials_outcomes",       "replace_by_nct_id"),
    TableConfig("officials",     "clinical_trials_officials",      "replace_by_nct_id"),
)

EMBEDDING_TABLE_CONFIG: tuple[TableConfig, ...] = (
    TableConfig("embeddings",    "clinical_trials_embeddings",     "replace_by_nct_id"),
)

# Structured eligibility (Stage A) — re-extracted per trial, so replace by nct_id.
ELIGIBILITY_TABLE_CONFIG: tuple[TableConfig, ...] = (
    TableConfig("eligibility_criteria", "clinical_trials_eligibility_criteria", "replace_by_nct_id"),
)
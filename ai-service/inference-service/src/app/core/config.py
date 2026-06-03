from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    LOGDIR: str = './logs'
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── GCP / BigQuery ────────────────────────────────────────────────────────
    gcp_project_id: str = "data-eng-470620"
    bq_dataset: str = "healthcare_ai"
    bq_staging_table: str = "clinical_trials_gov"
    bq_embeddings_table: str = "clinical_trials_embeddings"
    bq_locations_table: str =     "clinical_trials_locations"
    bq_mesh_terms_table: str =    "clinical_trials_mesh_terms"
    bq_arm_groups_table: str =    "clinical_trials_arm_groups"
    bq_interventions_table: str = "clinical_trials_interventions"
    bq_outcomes_table: str =      "clinical_trials_outcomes"
    bq_officials_table: str =     "clinical_trials_officials"
    google_application_credentials: Optional[str] = None
    vector_search_oversample_factor: int = 3

    # ── clinicalTrials.gov v2 API ─────────────────────────────────────────────
    ct_api_overall_statuses: str = "ENROLLING_BY_INVITATION,RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED"


    # ── HuggingFace embeddings ────────────────────────────────────────────────
    # sentence-transformers model; runs locally, no API key required.
    # nomic-embed-text-v1.5 → 768-dim, 8192-token context window (~137 MB).
    # Requires trust_remote_code=True.  Uses task prefixes:
    #   "search_document:" at index time, "search_query:" at query time.
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"

    @property
    def bq_full_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_staging_table}"
    @property
    def bq_full_locations_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_locations_table}"
    @property
    def bq_full_mesh_terms_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_mesh_terms_table}"
    @property
    def bq_full_arm_groups_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_arm_groups_table}"
    @property
    def bq_full_interventions_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_interventions_table}"
    @property
    def bq_full_outcomes_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_outcomes_table}"
    @property
    def bq_full_officials_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_officials_table}"
    @property
    def bq_embeddings_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_embeddings_table}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

from typing import Optional

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
    google_application_credentials: Optional[str] = None

    # ── clinicalTrials.gov v2 API ─────────────────────────────────────────────
    ct_api_base_url: str = "https://clinicaltrials.gov/api/v2"
    ct_api_page_size: int = 1000
    ct_api_max_loop: int = 100 # Max pages to yield trials i.e 1000 * 100 (ct_api_page_size * ct_api_max_loop)
    ct_api_max_retries: int = 5
    ct_api_overall_statuses: str = "ENROLLING_BY_INVITATION,RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED"


    bq_embeddings_table: str = "clinical_trials_embeddings"
    bq_eligibility_table: str = "clinical_trials_eligibility_criteria"

    # ── PostgreSQL (inference service read replica) ───────────────────────────
    # Set this to enable the Postgres sink alongside BigQuery.
    # Format: postgresql+psycopg://user:password@host:port/dbname
    pg_database_url: Optional[str] = None

    # ── GCS staging ───────────────────────────────────────────────────────────
    # Parquet files are written here before the BQ load jobs read them
    gcs_bucket: str = "bitziv_health_data"
    # Trial data Parquet files land under this prefix
    gcs_prefix: str = "clinical_trials"
    # Embedding Parquet files land under this separate prefix
    gcs_embeddings_prefix: str = "clinical_trials_embeddings"
    # Structured-eligibility Parquet files land under this separate prefix
    gcs_eligibility_prefix: str = "clinical_trials_eligibility_criteria"

    embedding_max_sequence_length: int = 8192

    # ── HuggingFace embeddings ────────────────────────────────────────────────
    # sentence-transformers model; runs locally, no API key required.
    # nomic-embed-text-v1.5 → 768-dim, 8192-token context window (~137 MB).
    # Requires trust_remote_code=True.  Uses task prefixes:
    #   "search_document:" at index time, "search_query:" at query time.
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    # 137 MB model; batch 16 is safe on CPU, raise to 32+ on GPU.
    embedding_batch_size: int = 16
    # Max trials per embedding sub-batch within a date-range chunk.
    # Bounds the in-memory chunk list (~5 chunks/trial × 200 = 1 000 chunks at a time).
    embedding_trial_batch_size: int = 200

    # ── Structured eligibility extraction (Stage A, ROADMAP step 3) ───────────
    # LLM splits eligibility_criteria into atomic, classified items. Extraction runs only
    # when a key is set; without it the step is skipped (no items emitted). Gate
    # re-extraction on the per-trial source_hash so the 590k-trial backfill is paid once.
    openai_api_key: Optional[str] = None
    eligibility_extract_model: str = "gpt-5-mini"

    @property
    def bq_full_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_staging_table}"

    @property
    def bq_embeddings_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_embeddings_table}"

    @property
    def bq_eligibility_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_eligibility_table}"

    @property
    def gcs_base_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_prefix}"

    @property
    def gcs_embeddings_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_embeddings_prefix}"

    @property
    def gcs_eligibility_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_eligibility_prefix}"


settings = Settings()

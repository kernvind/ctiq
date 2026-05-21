from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── GCP / BigQuery ────────────────────────────────────────────────────────
    gcp_project_id: str = "data-eng-470620"
    bq_dataset: str = "healthcare_ai"
    bq_staging_table: str = "clinical_trials_gov_stg"
    google_application_credentials: Optional[str] = None

    # ── clinicalTrials.gov v2 API ─────────────────────────────────────────────
    ct_api_base_url: str = "https://clinicaltrials.gov/api/v2"
    ct_api_page_size: int = 1000
    ct_api_max_retries: int = 5
    ct_api_overall_statuses: str = "ENROLLING_BY_INVITATION,RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED"

    # ── Parallelism ───────────────────────────────────────────────────────────
    # Number of Dask worker threads for concurrent API calls
    dask_n_workers: int = 8
    # Each Dask task covers this many days of lastUpdatePostDate range
    date_range_chunk_days: int = 90

    bq_embeddings_table: str = "clinical_trials_gov_embeddings_stg"

    # ── GCS staging ───────────────────────────────────────────────────────────
    # Parquet files are written here before the BQ load jobs read them
    gcs_bucket: str = "bitziv_health_data"
    # Trial data Parquet files land under this prefix
    gcs_prefix: str = "clinical_trials_gov_stg"
    # Embedding Parquet files land under this separate prefix
    gcs_embeddings_prefix: str = "clinical_trials_gov_embeddings_stg"

    # ── HuggingFace embeddings ────────────────────────────────────────────────
    # sentence-transformers model; runs locally, no API key required.
    # nomic-embed-text-v1.5 → 768-dim, 8192-token context window (~137 MB).
    # Requires trust_remote_code=True.  Uses task prefixes:
    #   "search_document:" at index time, "search_query:" at query time.
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"
    # 8192-token window → 6000-char chunks keep most trials in 1-2 chunks.
    embedding_chunk_size: int = 6000
    embedding_chunk_overlap: int = 600
    # 137 MB model; batch 32 is safe on CPU, raise to 64+ on GPU.
    embedding_batch_size: int = 32

    @property
    def bq_full_table_id(self) -> str:
        return f"{self.gcp_project_id}.{self.bq_dataset}.{self.bq_staging_table}"

    @property
    def gcs_base_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_prefix}"

    @property
    def gcs_embeddings_uri(self) -> str:
        return f"gs://{self.gcs_bucket}/{self.gcs_embeddings_prefix}"


settings = Settings()

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LOGDIR: str = "./logs"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    pg_database_url: str = "postgresql://localhost/ctiq"

    # ── Vector search ─────────────────────────────────────────────────────────
    vector_search_oversample_factor: int = 3

    # ── clinicalTrials.gov v2 API ─────────────────────────────────────────────
    ct_api_overall_statuses: str = (
        "ENROLLING_BY_INVITATION,RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED"
    )

    # ── HuggingFace embeddings ────────────────────────────────────────────────
    embedding_model_name: str = "nomic-ai/nomic-embed-text-v1.5"

    @property
    def asyncpg_database_url(self) -> str:
        """Strip SQLAlchemy driver prefix so asyncpg can use the URL directly."""
        url = self.pg_database_url
        for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://"):
            if url.startswith(prefix):
                return url.replace(prefix, "postgresql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

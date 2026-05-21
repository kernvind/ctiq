"""
Pydantic model for the clinical_trials_gov_embeddings_stg table.

Schema:
    nct_id       STRING  NOT NULL
    startDate    DATE    NOT NULL
    chunk_index  INT64   NOT NULL
    text_chunk   STRING  NOT NULL
    embeddings   ARRAY<FLOAT64>

Partitioned by DATE_TRUNC(startDate, MONTH), clustered by nct_id.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class TrialEmbeddingChunk(BaseModel):
    nct_id: str
    startDate: date
    chunk_index: int
    text_chunk: str
    embeddings: list[float]

    def to_bq_row(self) -> dict:
        return {
            "nct_id": self.nct_id,
            "startDate": self.startDate.isoformat(),
            "chunk_index": self.chunk_index,
            "text_chunk": self.text_chunk,
            "embeddings": self.embeddings,
        }

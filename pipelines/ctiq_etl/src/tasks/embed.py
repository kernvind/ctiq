"""
Embed task: chunk trial text → generate embeddings locally → load to BQ.

Chunking strategy
-----------------
For each trial we build one document that captures identity, eligibility,
interventions, and description, then split it into overlapping windows of
``settings.embedding_chunk_size`` characters with ``settings.embedding_chunk_overlap``
character overlap.

Embedding model
---------------
``nomic-ai/nomic-embed-text-v1.5`` runs locally (no API key, ~137 MB).
Output: 768-dim FLOAT32 vectors, stored as FLOAT64 in BQ ARRAY<FLOAT64>.
8192-token context window — most complete trial documents fit in 1-2 chunks.
Requires ``trust_remote_code=True``.  Task prefixes are used:
  index time → prompt_name="document"  (prepends "search_document: ")
  query time → prompt_name="query"     (prepends "search_query: ")
The model is downloaded from HuggingFace Hub on first use and cached at
~/.cache/huggingface/hub/.

BigQuery vector search usage (after load):
    SELECT base.nct_id, distance
    FROM VECTOR_SEARCH(
        TABLE `healthcare_ai.clinical_trials_gov_embeddings_stg`,
        'embeddings',
        (SELECT @query_embedding AS embeddings),
        top_k => 10,
        distance_type => 'COSINE'
    )
    ORDER BY distance
"""
from __future__ import annotations

import io
import logging
import uuid
from datetime import date
from functools import lru_cache
from typing import Literal, Optional

import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import bigquery, storage
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.models.embedding import TrialEmbeddingChunk
from src.models.trial import ClinicalTrial

logger = logging.getLogger(__name__)

WriteDisposition = Literal["WRITE_TRUNCATE", "WRITE_APPEND"]


# ── Model singleton ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """
    Load the SentenceTransformer model once per process.

    ``lru_cache`` ensures we don't reload the model on every batch call,
    which is expensive (~150 MB, several seconds on CPU).
    """
    logger.info("Loading embedding model: %s", settings.embedding_model_name)
    # trust_remote_code=True is required by nomic-embed-text-v1.5
    model = SentenceTransformer(settings.embedding_model_name, trust_remote_code=True)
    logger.info(
        "Model loaded — output dims: %d", model.get_embedding_dimension()
    )
    return model


# ── Text document builder ──────────────────────────────────────────────────────

def _build_document(trial: ClinicalTrial) -> str:
    """
    Combine the most semantically rich fields into one labelled text document.
    Labels help the model distinguish sections even after chunking.
    """
    sections: list[str] = []

    if trial.officialTitle:
        sections.append(f"TITLE: {trial.officialTitle}")

    if trial.conditionsModule:
        sections.append(f"CONDITIONS: {', '.join(trial.conditionsModule)}")

    if trial.overallStatus:
        sections.append(f"STATUS: {trial.overallStatus}")

    if trial.designModule_studyType:
        sections.append(f"STUDY TYPE: {trial.designModule_studyType}")

    if trial.designModule_designInfo_primaryPurpose:
        sections.append(f"PRIMARY PURPOSE: {trial.designModule_designInfo_primaryPurpose}")

    if trial.armsInterventionsModule_interventions:
        lines = [
            f"  - [{iv.type}] {iv.name}: {iv.description or ''}"
            for iv in trial.armsInterventionsModule_interventions
        ]
        sections.append("INTERVENTIONS:\n" + "\n".join(lines))

    if trial.outcomesModule_primaryOutcomes:
        lines = [
            f"  - {o.measure} ({o.timeFrame or 'N/A'})"
            for o in trial.outcomesModule_primaryOutcomes
        ]
        sections.append("PRIMARY OUTCOMES:\n" + "\n".join(lines))

    if trial.eligibilityCriteria:
        sections.append(f"ELIGIBILITY:\n{trial.eligibilityCriteria}")

    if trial.detailedDescription:
        sections.append(f"DESCRIPTION:\n{trial.detailedDescription}")

    return "\n\n".join(sections)


# ── Text chunker ───────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split *text* into overlapping windows, breaking at word boundaries.

    Note: nomic-embed-text-v1.5 has an 8192-token input limit.  At ~4
    chars/token that's ~32k chars.  Default chunk_size is 6000 chars, which
    lets most complete trial documents fit in 1-2 chunks.
    """
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


# ── Embedding call ─────────────────────────────────────────────────────────────

def _embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Encode *texts* with the local SentenceTransformer model.

    Uses the ``document`` prompt so nomic prepends the required
    "search_document: " task prefix automatically.  At query time, the
    caller must use ``prompt_name="query"`` (or manually prepend
    "search_query: ") for cosine similarity to be meaningful.

    Returns a list of float64 vectors (Python float, not numpy float32)
    so they serialize correctly to BQ ARRAY<FLOAT64>.
    """
    model = _get_model()
    embeddings = model.encode(
        texts,
        prompt_name="document",
        batch_size=settings.embedding_batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    # numpy float32 → Python float (64-bit) for BQ ARRAY<FLOAT64>
    return [row.astype(float).tolist() for row in embeddings]


# ── Main: chunk + embed ────────────────────────────────────────────────────────

def generate_trial_chunks(trials: list[ClinicalTrial]) -> list[TrialEmbeddingChunk]:
    """
    For each trial:
      1. Build a labelled text document from the most relevant fields.
      2. Split into overlapping chunks.
      3. Batch-embed all chunks with the local sentence-transformer model.

    Returns a flat list of TrialEmbeddingChunk objects ready to load.
    """
    # ── Collect all chunks ────────────────────────────────────────────────────
    all_chunks: list[tuple[str, int, str]] = []  # (nct_id, chunk_index, text)
    start_dates: dict[str, "date"] = {}

    for trial in trials:
        doc = _build_document(trial)
        chunks = _chunk_text(doc, settings.embedding_chunk_size, settings.embedding_chunk_overlap)
        start_dates[trial.nct_id] = trial.startDate
        for idx, chunk in enumerate(chunks):
            all_chunks.append((trial.nct_id, idx, chunk))

    logger.info("Generated %d text chunks from %d trials", len(all_chunks), len(trials))
    if not all_chunks:
        return []

    # ── Embed in batches ──────────────────────────────────────────────────────
    texts = [c[2] for c in all_chunks]
    all_vectors = _embed_batch(texts)  # single encode() call handles batching internally

    logger.info(
        "Embedded %d chunks  |  dims=%d  |  model=%s",
        len(all_vectors),
        len(all_vectors[0]) if all_vectors else 0,
        settings.embedding_model_name,
    )

    # ── Assemble TrialEmbeddingChunk objects ──────────────────────────────────
    return [
        TrialEmbeddingChunk(
            nct_id=nct_id,
            startDate=start_dates[nct_id],
            chunk_index=chunk_index,
            text_chunk=text_chunk,
            embeddings=vector,
        )
        for (nct_id, chunk_index, text_chunk), vector in zip(all_chunks, all_vectors)
    ]


# ── Parquet schema for embeddings table ───────────────────────────────────────

EMBEDDING_PARQUET_SCHEMA = pa.schema(
    [
        pa.field("nct_id", pa.string(), nullable=False),
        pa.field("startDate", pa.date32(), nullable=False),
        pa.field("chunk_index", pa.int64(), nullable=False),
        pa.field("text_chunk", pa.large_string(), nullable=False),
        pa.field("embeddings", pa.list_(pa.float64())),
    ]
)


def _chunks_to_arrow_table(chunks: list[TrialEmbeddingChunk]) -> pa.Table:
    rows = [c.to_bq_row() for c in chunks]

    def col(name: str):
        return [r[name] for r in rows]

    start_dates_parsed = [
        date.fromisoformat(d) if isinstance(d, str) else d for d in col("startDate")
    ]

    return pa.table(
        {
            "nct_id": pa.array(col("nct_id"), type=pa.string()),
            "startDate": pa.array(start_dates_parsed, type=pa.date32()),
            "chunk_index": pa.array(col("chunk_index"), type=pa.int64()),
            "text_chunk": pa.array(col("text_chunk"), type=pa.large_string()),
            "embeddings": pa.array(col("embeddings"), type=pa.list_(pa.float64())),
        },
        schema=EMBEDDING_PARQUET_SCHEMA,
    )


# ── GCS upload + BQ load ───────────────────────────────────────────────────────

def upload_embeddings_chunk_to_gcs(
    chunks: list[TrialEmbeddingChunk],
    run_id: str,
    chunk_idx: int,
) -> None:
    """
    Serialize *chunks* to a single Parquet file and upload to GCS.

    GCS path: {embeddings_prefix}/{run_id}/chunk_{chunk_idx:04d}.parquet
    BQ wildcard: {embeddings_prefix}/{run_id}/chunk_*.parquet  (single *, BQ-compatible)

    Call once per streaming chunk; call ``bq_load_embeddings`` once after all
    chunks are uploaded.
    """
    if not chunks:
        logger.debug("upload_embeddings_chunk: empty list for chunk %d — skipping", chunk_idx)
        return

    arrow_table = _chunks_to_arrow_table(chunks)
    buf = io.BytesIO()
    pq.write_table(arrow_table, buf, compression="snappy")
    buf.seek(0)

    blob_name = f"{settings.gcs_embeddings_prefix}/{run_id}/chunk_{chunk_idx:04d}.parquet"
    gcs_client = storage.Client(project=settings.gcp_project_id)
    bucket = gcs_client.bucket(settings.gcs_bucket)
    bucket.blob(blob_name).upload_from_file(buf, content_type="application/octet-stream")

    logger.info(
        "Uploaded gs://%s/%s  (%d embedding rows)",
        settings.gcs_bucket,
        blob_name,
        arrow_table.num_rows,
    )


def bq_load_embeddings(
    run_id: str,
    write_disposition: WriteDisposition,
) -> Optional[int]:
    """
    Trigger a single BigQuery load job over all embedding Parquet files
    uploaded for *run_id*.

    Uses a single-wildcard URI (chunk_*.parquet) which BQ supports.
    Call once after all chunks have been uploaded via ``upload_embeddings_chunk_to_gcs``.
    """
    wildcard_uri = (
        f"gs://{settings.gcs_bucket}/{settings.gcs_embeddings_prefix}/{run_id}/chunk_*.parquet"
    )
    logger.info("All embedding partitions uploaded  |  wildcard=%s", wildcard_uri)

    bq_client = bigquery.Client(project=settings.gcp_project_id)
    embeddings_table = (
        f"{settings.gcp_project_id}.{settings.bq_dataset}.{settings.bq_embeddings_table}"
    )
    table_ref = bigquery.TableReference.from_string(embeddings_table)

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=getattr(bigquery.WriteDisposition, write_disposition),
        autodetect=False,
    )
    load_job = bq_client.load_table_from_uri(wildcard_uri, table_ref, job_config=job_config)
    logger.info("BQ embeddings load job started: %s", load_job.job_id)
    load_job.result()

    result_table = bq_client.get_table(table_ref)
    logger.info(
        "BQ embeddings load complete  |  table now has %d rows", result_table.num_rows
    )
    return load_job.output_rows

from __future__ import annotations
 
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
from src.config import settings
from src.tasks.load.bq import get_existing_embeddings_hash
import torch
from sentence_transformers import SentenceTransformer
 
logger = logging.getLogger(__name__)

 
# Nomic task prefixes — must match between index and query time.
INDEX_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

 
def _title_text(trial: dict) -> Optional[str]:
    """Brief title preferred; falls back to official title."""
    return trial.get("brief_title") or trial.get("official_title")

def _summary_text(trial: dict) -> Optional[str]:
    """
    Composite 'summary' document for general discovery and 'find similar trials'.
 
    Deliberately excludes enums (status, phase, allocation, masking,
    primary_purpose, study_type). Those are SQL pre-filters at query time;
    encoding them into the embedding wastes capacity and forces re-embed
    when status changes from RECRUITING -> COMPLETED.
    """
    parts: list[str] = []
    if trial.get("official_title"):
        parts.append(f"TITLE: {trial['official_title']}")
    if trial.get("conditions"):
        parts.append(f"CONDITIONS: {', '.join(trial['conditions'])}")
    if trial.get("keywords"):
        parts.append(f"KEYWORDS: {', '.join(trial['keywords'])}")
    if trial.get("brief_summary"):
        parts.append(f"SUMMARY:\n{trial['brief_summary']}")
    if trial.get("detailed_description"):
        parts.append(f"DESCRIPTION:\n{trial['detailed_description']}")
    return "\n\n".join(parts) if parts else None
 
 
def _outcome_text(outcome: dict) -> str:
    parts = []
    if outcome.get("measure"):
        parts.append(outcome["measure"])
    if outcome.get("description"):
        parts.append(outcome["description"])
    if outcome.get("time_frame"):
        parts.append(f"(Time frame: {outcome['time_frame']})")
    return " ".join(parts).strip()
 
 
def _intervention_text(intervention: dict) -> str:
    parts = []
    if intervention.get("name"):
        parts.append(intervention["name"])
    if intervention.get("other_names"):
        parts.append(f"(also known as: {', '.join(intervention['other_names'])})")
    if intervention.get("description"):
        parts.append(intervention["description"])
    return " ".join(parts).strip()
 
 
def _hash_text(text: str) -> str:
    """SHA-256 of raw chunk text (no prefix) for change detection."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# ─── Chunk extraction ────────────────────────────────────────────────────────
 
@dataclass
class EmbeddingChunk:
    """One text chunk awaiting embedding."""
    nct_id: str
    field_type: str
    chunk_id: int
    chunk_text: str  # without the task prefix
 
 
def extract_chunks(transformed: dict) -> list[EmbeddingChunk]:
    """
    Produce all chunks to embed for one trial.
 
    Input is the dict returned by transform_study(), with keys
    {'trial', 'outcomes', 'interventions', ...}.
    """
    trial = transformed["trial"]
    nct_id = trial["nct_id"]
    chunks: list[EmbeddingChunk] = []
 
    if (title := _title_text(trial)):
        chunks.append(EmbeddingChunk(nct_id, "title", 0, title))
 
    if (summary := _summary_text(trial)):
        chunks.append(EmbeddingChunk(nct_id, "summary", 0, summary))

    # Per-item eligibility chunks are NOT built here — they come from the Stage A
    # extractor's classified items (eligibility_item_chunks), so the split has a single
    # source of truth. They're merged into the batch in embed_trials.

    for i, outcome in enumerate(transformed.get("outcomes") or []):
        text = _outcome_text(outcome)
        if text:
            chunks.append(EmbeddingChunk(nct_id, "outcome", i, text))
 
    for i, intervention in enumerate(transformed.get("interventions") or []):
        text = _intervention_text(intervention)
        if text:
            chunks.append(EmbeddingChunk(nct_id, "intervention", i, text))
 
    return chunks


# Field types for the two per-criterion eligibility embeddings. Must match the inference
# planner's Field enum values (eligibility_inclusion / eligibility_exclusion).
_ELIGIBILITY_FIELD_TYPE = {
    "inclusion": "eligibility_inclusion",
    "exclusion": "eligibility_exclusion",
}


def eligibility_item_chunks(eligibility_rows: list[dict]) -> list[EmbeddingChunk]:
    """Build per-item eligibility embedding chunks from Stage A criterion rows.

    Inclusion/exclusion → distinct field_type (so the planner can match inclusion only).
    `chunk_id` = the criterion's `display_order`, so a matched embedding joins straight back
    to its `trial_eligibility_criteria` row (category/predicate/confidence) for explanation.
    Boilerplate (`is_actionable` False) is not embedded.
    """
    chunks: list[EmbeddingChunk] = []
    for row in eligibility_rows:
        if not row.get("is_actionable"):
            continue
        text = (row.get("text") or "").strip()
        criterion_type = row.get("criterion_type")
        if not isinstance(criterion_type, str):
            continue
        field_type = _ELIGIBILITY_FIELD_TYPE.get(criterion_type)
        if not text or field_type is None:
            continue
        chunks.append(EmbeddingChunk(row["nct_id"], field_type, row["display_order"], text))
    return chunks


# ─── Embedder ────────────────────────────────────────────────────────────────

_embedder_instance: Optional["TrialEmbedder"] = None

def get_embedder() -> "TrialEmbedder":
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = TrialEmbedder()
    return _embedder_instance


class TrialEmbedder:
    """
    Sentence-Transformers wrapper specialized for clinical trial chunks.
 
    The model is loaded once at __init__ and reused across calls. GPU is
    auto-selected if available; pass device='cpu' to force CPU.
    """
 
    def __init__(
        self,
        model_name: str = settings.embedding_model_name,
        device: Optional[str] = None,
        max_seq_length: int = settings.embedding_max_sequence_length,
    ):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        logger.info("Loading embedding model %s on %s", model_name, device)
        # GPU memory is batch_size × seq_len² sensitive — stay conservative at 8192 tokens
        _default_batch = {"cuda": 8, "mps": 16, "cpu": 32}
        self._default_batch_size = _default_batch.get(device, 32)
        self.model = SentenceTransformer(
            model_name,
            trust_remote_code=True,
            device=device,
        )
        self.model.max_seq_length = max_seq_length
        self.model_name = model_name
        # Use the HF model id as the version string. If you fine-tune or
        # change the truncation dim, append a suffix here so old/new vectors
        # don't get mixed in BQ.
        self.model_version = model_name
 
    def embed_chunks(
        self,
        chunks: list[EmbeddingChunk],
        batch_size: int = settings.embedding_batch_size,
        show_progress: bool = False,
    ) -> list[dict]:
        """
        Embed a batch of chunks and return rows for the embeddings table.
 
        Applies the index-time prefix automatically. Output vectors are
        L2-normalized so cosine similarity equals dot product downstream.
        """
        if not chunks:
            return []
 
        prefixed_texts = [INDEX_PREFIX + c.chunk_text for c in chunks]
 
        vectors = self.model.encode(
            prefixed_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress,
            normalize_embeddings=True,
        )
 
        now = datetime.now(timezone.utc)
        rows: list[dict] = []
        for chunk, vec in zip(chunks, vectors):
            # Strip NUL (0x00) — Postgres text columns reject it; can appear in source prose.
            chunk_text = chunk.chunk_text.replace("\x00", "")
            rows.append({
                "nct_id": chunk.nct_id,
                "field_type": chunk.field_type,
                "chunk_id": chunk.chunk_id,
                "chunk_text": chunk_text,
                "source_hash": _hash_text(chunk_text),
                "embedding": vec.tolist(),
                "model_version": self.model_version,
                "ingested_at": now,
           })
        return rows
 
    def embed_trials(
        self,
        transformed_studies: Iterable[dict],
        batch_size: int = settings.embedding_batch_size,
        show_progress: bool = False,
        skip_existing_check: bool = False,
        eligibility_rows: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Convenience: extract chunks from each study and embed them all.

        `eligibility_rows` (Stage A criterion rows) are turned into per-item eligibility
        chunks and embedded in the SAME batch as the trial's other chunks — so all of a
        trial's vectors are written by one replace-by-nct_id upsert and nothing clobbers.
        """
        all_chunks: list[EmbeddingChunk] = []
        nct_ids = set()
        batch_size =  self._default_batch_size or batch_size
        for transformed in transformed_studies:
            if not transformed:
                continue
            nct_ids.add(transformed.get("trial", {}).get("nct_id", ""))
            all_chunks.extend(extract_chunks(transformed))

        if eligibility_rows:
            all_chunks.extend(eligibility_item_chunks(eligibility_rows))
            nct_ids.update(row["nct_id"] for row in eligibility_rows)

        if skip_existing_check:
            to_embed = all_chunks
        else:
            existing_embeddings = get_existing_embeddings_hash(nct_ids=list(nct_ids))
            to_embed = []
            for chunk in all_chunks:
                key = (chunk.nct_id, chunk.field_type, chunk.chunk_id)
                if existing_embeddings.get(key) == _hash_text(chunk.chunk_text):
                    logger.info("Skipping embedding for %s (unchanged since last run)", key)
                    continue
                to_embed.append(chunk)

        return self.embed_chunks(
            to_embed,
            batch_size=batch_size,
            show_progress=show_progress,
        )
 
    def embed_query(self, query: str) -> list[float]:
        """
        Embed a user query for retrieval. Uses the 'search_query: ' prefix —
        critical for alignment with index-side embeddings.
        """
        vec = self.model.encode(
            QUERY_PREFIX + query,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return vec.tolist()
"""Stage A structured-eligibility extraction (Asset 1 — docs/ROADMAP.md step 3).

Splits the free-text `eligibility_criteria` blob into atomic, classified assertions ready
to land in `trials.trial_eligibility_criteria`. Mirrors the inference-service query
planner's contract: an LLM with structured outputs (`responses.parse`) producing a typed
Pydantic model, with the OpenAI client injected so this stays unit-testable offline.

Scope is **Stage A only**: split + classify (criterion_type, category, subtype,
confidence, is_actionable, source_bullet_index). The normalized `predicate` (Stage B) is
deliberately *not* part of this schema — it's filled in later, category by category.

NOTE: wiring these rows into the load path (parquet → BQ → Postgres) and adding the
`field_type="eligibility_item"` embeddings is a follow-up; this module owns extraction and
the in-memory → DB-row mapping only.
"""
from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from enum import Enum
from typing import Iterable, Literal, Optional

from pydantic import BaseModel, Field

from src.config import settings

logger = logging.getLogger(__name__)

# Reuse the planner's model unless overridden; cheap structured-output model.
_DEFAULT_MODEL = "gpt-5-mini"


class CriterionCategory(str, Enum):
    """The eligibility taxonomy (validated against real CT.gov prose; see ROADMAP step 3).

    `OTHER` is the explicit fallback — never force a fit; use `subtype` to name it.
    """

    DIAGNOSIS = "diagnosis"
    DISEASE_STAGE = "disease_stage"
    BIOMARKER = "biomarker"
    PRIOR_THERAPY = "prior_therapy"
    PERFORMANCE_STATUS = "performance_status"
    DEMOGRAPHIC = "demographic"
    LAB_VALUE = "lab_value"
    DISEASE_ASSESSMENT = "disease_assessment"
    COMORBIDITY = "comorbidity"
    CONCOMITANT_MED = "concomitant_med"
    REPRODUCTIVE = "reproductive"
    CONSENT_LOGISTICS = "consent_logistics"
    OTHER = "other"


class Predicate(BaseModel):
    """Stage B: the normalized, machine-comparable form of a criterion — one flat object
    covering the enumerable categories. Only the fields relevant to a criterion's category
    are filled; the rest stay null. Prose-y categories (comorbidity, diagnosis, …) get no
    predicate at all (null on ExtractedCriterion).

    Field → category guide:
      biomarker:           marker, qualifier, assay, op, value, unit, relation, unknown_status
      performance_status:  scale, min, max
      disease_stage:       stage, modifiers
      prior_therapy:       therapy_class, relation, max_lines
      demographic:         min, max, unit
      lab_value:           analyte, op, value, unit
    """

    marker: Optional[str] = None              # gene/protein, e.g. EGFR, PD-L1
    qualifier: Optional[str] = None           # e.g. "sensitizing", "activating"
    assay: Optional[str] = None               # e.g. "VENTANA SP263"
    scale: Optional[str] = None               # performance status scale, e.g. ECOG
    analyte: Optional[str] = None             # lab analyte, e.g. ANC, creatinine
    therapy_class: Optional[str] = None       # e.g. "EGFR TKI", "checkpoint inhibitor"
    op: Optional[Literal[">=", "<=", ">", "<", "==", "!="]] = None
    value: Optional[float] = None
    unit: Optional[str] = None                # e.g. "%TC", "/uL", "years"
    min: Optional[float] = None               # inclusive range low (e.g. ECOG/age)
    max: Optional[float] = None               # inclusive range high
    max_lines: Optional[int] = None           # prior_therapy line cap
    stage: Optional[list[str]] = None         # e.g. ["IV"], ["IIIA","IIIB"]
    modifiers: Optional[list[str]] = None     # e.g. ["metastatic","recurrent"]
    relation: Optional[Literal["required", "excluded", "allowed", "prohibited"]] = None
    # When the marker's status is unknown/untested, is the patient eligible or excluded?
    unknown_status: Optional[Literal["eligible", "excluded"]] = None


class ExtractedCriterion(BaseModel):
    """One atomic eligibility assertion. Maps 1:1 onto a trial_eligibility_criteria row."""

    criterion_type: Literal["inclusion", "exclusion"]
    # Verbatim text of the single assertion — NOT the whole source bullet. One compound
    # bullet ("Stage IV NSCLC with no prior therapy") yields several of these.
    text: str
    category: CriterionCategory
    # Free-text refinement: required when category is OTHER; optional detail elsewhere.
    subtype: Optional[str] = None
    # Stage B normalized predicate — populated only for enumerable categories, else null.
    predicate: Optional[Predicate] = None
    # Self-reported confidence in [0, 1]; low values feed the downstream "uncertain" bucket.
    confidence: float = Field(ge=0.0, le=1.0)
    # False for boilerplate like "Other protocol-defined criteria apply" — never a filter.
    is_actionable: bool
    # 0-based index of the source bullet this assertion was split from (compound-bullet trace).
    source_bullet_index: int


class ExtractedEligibility(BaseModel):
    """Top-level structured-output container the LLM returns."""

    criteria: list[ExtractedCriterion]


_SYSTEM_PROMPT = """\
You convert a clinical trial's free-text eligibility criteria into a list of atomic, \
classified assertions. You only restructure the given text — never invent, infer beyond \
what is written, or give medical advice.

Rules:
- SPLIT compound items. One source bullet often bundles several assertions \
(e.g. "histologically confirmed Stage IV NSCLC with no prior systemic therapy" = three: \
a diagnosis, a disease_stage, and a prior_therapy). Emit one object per atomic assertion.
- Set source_bullet_index to the 0-based index of the bullet the assertion came from \
(bullets in order, inclusion then exclusion).
- Set criterion_type from the section the bullet is under (inclusion vs exclusion).
- Set text to the verbatim span of the single assertion (trim, do not paraphrase).
- Classify category into exactly one of: diagnosis, disease_stage, biomarker, \
prior_therapy, performance_status, demographic, lab_value, disease_assessment, \
comorbidity, concomitant_med, reproductive, consent_logistics, other. Use `other` (with a \
short `subtype`) rather than forcing a poor fit.
- Set is_actionable=false for boilerplate that is not a real filter (e.g. "Other \
protocol-defined inclusion/exclusion criteria apply", "willing and able to provide \
informed consent" is consent_logistics and actionable=true; pure boilerplate is not).
- confidence in [0,1] reflects how cleanly the assertion classified.
- predicate: fill the normalized predicate ONLY for these categories (leave fields you \
cannot ground in the text null); for ALL other categories set predicate to null:
  * biomarker: marker (gene/protein), qualifier (e.g. "sensitizing"), assay, op+value+unit \
(e.g. PD-L1 >= 1 %TC), relation ("required" for inclusion, "excluded" for exclusion), and \
unknown_status ("eligible"/"excluded") when the text states how unknown/untested status is treated.
  * performance_status: scale (e.g. "ECOG") + min/max ("ECOG 0-1" -> min 0, max 1).
  * disease_stage: stage (e.g. ["IV"]) + modifiers (e.g. ["metastatic","recurrent"]).
  * prior_therapy: therapy_class, relation ("prohibited"/"required"/"allowed"), max_lines if a line cap is stated.
  * demographic: min/max + unit (age in "years").
  * lab_value: analyte + op + value + unit.
  Never invent values not present in the text."""


# Bump when the prompt or output schema changes so the source_hash gate re-extracts
# everything instead of silently skipping (the hash is over the input blob, not the output).
_EXTRACTOR_VERSION = "2-predicates"


def eligibility_source_hash(text: str) -> str:
    """Version-salted SHA-256 of the raw eligibility blob — gate re-extraction on this.
    Salting with the extractor version means a prompt/schema change invalidates old hashes,
    so the next run re-extracts (e.g. to backfill Stage B predicates) rather than skipping."""
    return hashlib.sha256(f"{_EXTRACTOR_VERSION}\x1f{text}".encode("utf-8")).hexdigest()


class EligibilityExtractor:
    """LLM-backed Stage A extractor. Client injected (OpenAI sync client) for testability.

    Usage (caller owns the OpenAI client + the source_hash cache):

        from openai import OpenAI
        extractor = EligibilityExtractor(OpenAI(api_key=...), model="gpt-5-mini")
        items = extractor.extract(trial["eligibility_criteria"])
    """

    def __init__(self, client, model: str = _DEFAULT_MODEL):
        self._client = client
        self._model = model

    def extract(self, eligibility_text: Optional[str]) -> list[ExtractedCriterion]:
        """Return atomic, classified criteria for one trial. Empty list when there's no
        text or the model declines (fail-soft — never raise into the ETL transform)."""
        text = (eligibility_text or "").strip()
        if not text:
            return []
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=_SYSTEM_PROMPT,
                input=text,
                text_format=ExtractedEligibility,
            )
        except Exception:
            logger.warning("Eligibility extraction failed; emitting no items", exc_info=True)
            return []

        parsed = response.output_parsed
        if parsed is None:
            logger.warning("Eligibility extraction: model returned no parse")
            return []
        return parsed.criteria


_extractor_instance: Optional["EligibilityExtractor"] = None


def get_eligibility_extractor() -> Optional["EligibilityExtractor"]:
    """Singleton extractor built from settings. Returns None when no OpenAI key is set —
    callers skip extraction entirely in that case (mirrors the embeddings skip path)."""
    global _extractor_instance
    if not settings.openai_api_key:
        return None
    if _extractor_instance is None:
        from openai import OpenAI

        _extractor_instance = EligibilityExtractor(
            OpenAI(api_key=settings.openai_api_key),
            model=settings.eligibility_extract_model,
        )
    return _extractor_instance


def collect_pending(
    transformed_studies: Iterable[dict],
    skip_existing_check: bool = False,
) -> dict[str, tuple[str, str]]:
    """Index trials needing extraction → {nct_id: (eligibility_text, source_hash)}.

    Trims/skips trials with no eligibility text and, unless skip_existing_check, drops trials
    whose blob hash is unchanged since the last run (the source_hash re-extract gate). Shared
    by the inline and batch paths so the gating logic lives in one place.
    """
    pending: dict[str, tuple[str, str]] = {}
    for transformed in transformed_studies:
        if not transformed:
            continue
        trial = transformed.get("trial", {})
        nct_id = trial.get("nct_id")
        text = (trial.get("eligibility_criteria") or "").strip()
        if not nct_id or not text:
            continue
        pending[nct_id] = (text, eligibility_source_hash(text))

    if pending and not skip_existing_check:
        from src.tasks.load.bq import get_existing_eligibility_hash

        existing = get_existing_eligibility_hash(nct_ids=list(pending))
        for nct_id, (_, source_hash) in list(pending.items()):
            if existing.get(nct_id) == source_hash:
                logger.info("Skipping eligibility for %s (unchanged since last run)", nct_id)
                del pending[nct_id]
    return pending


def lupd_map(studies: list[dict]) -> dict[str, object]:
    """Map nct_id → the trial's last_update_post_date (provenance for criterion rows).
    Shared by the inline and batch paths so both stamp the same value."""
    return {
        s["trial"]["nct_id"]: s["trial"].get("last_update_post_date")
        for s in studies if s and s.get("trial", {}).get("nct_id")
    }


def extract_trials(
    transformed_studies: Iterable[dict],
    ingestion_date: date,
    skip_existing_check: bool = False,
) -> list[dict]:
    """Inline extraction → trial_eligibility_criteria rows. Requests run **concurrently**
    (thread pool, size = settings.eligibility_extract_concurrency) — same cost as serial,
    but ~Nx faster wall-clock. For the 590k backfill prefer the Batch API path
    (eligibility_batch.py), which is ~50% cheaper. No-ops to [] when no key is configured.
    """
    extractor = get_eligibility_extractor()
    if extractor is None:
        logger.info("Eligibility extraction skipped: no OpenAI key configured")
        return []

    studies = list(transformed_studies)  # materialize: iterated twice (pending + provenance)
    lupd_by_nct = lupd_map(studies)  # carry trial last_update_post_date onto criterion rows
    pending = collect_pending(studies, skip_existing_check)
    if not pending:
        return []

    workers = max(1, settings.eligibility_extract_concurrency)

    def _extract_one(item: tuple[str, tuple[str, str]]):
        nct_id, (text, source_hash) = item
        return nct_id, source_hash, extractor.extract(text)

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for nct_id, source_hash, items in pool.map(_extract_one, pending.items()):
            if items:
                rows.extend(
                    to_db_rows(
                        nct_id, items, source_hash=source_hash, ingestion_date=ingestion_date,
                        last_update_post_date=lupd_by_nct.get(nct_id),
                    )
                )
    logger.info(
        "Eligibility extraction (inline, %d workers): %d trials → %d criterion rows",
        workers, len(pending), len(rows),
    )
    return rows


def _no_nul(value):
    """Strip NUL (0x00) bytes — PostgreSQL text/varchar columns reject them, and they
    occasionally slip in via the source eligibility prose / model output."""
    return value.replace("\x00", "") if isinstance(value, str) else value


def to_db_rows(
    nct_id: str,
    items: list[ExtractedCriterion],
    *,
    source_hash: str,
    ingestion_date,
    last_update_post_date=None,
) -> list[dict]:
    """Map extracted criteria to trial_eligibility_criteria column dicts (load-path ready).

    `predicate` is intentionally omitted (Stage B). `display_order` preserves emit order.
    String fields are NUL-stripped so Postgres accepts them (also fixes the downstream
    embedding chunk_text, which derives from these rows).
    """
    return [
        {
            "nct_id": nct_id,
            "criterion_type": item.criterion_type,
            "text": _no_nul(item.text),
            "category": item.category.value,
            "subtype": _no_nul(item.subtype),
            # Stage B predicate → JSONB (drop null fields). PG-only for now (the parquet/BQ
            # eligibility schema omits `predicate`, so this key is ignored there).
            "predicate": item.predicate.model_dump(exclude_none=True) if item.predicate else None,
            "confidence": item.confidence,
            "is_actionable": item.is_actionable,
            "source_bullet_index": item.source_bullet_index,
            "source_hash": source_hash,
            "display_order": order,
            "ingestion_date": ingestion_date,
            "last_update_post_date": last_update_post_date,
        }
        for order, item in enumerate(items)
    ]

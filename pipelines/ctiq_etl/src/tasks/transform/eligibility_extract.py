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
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

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


class ExtractedCriterion(BaseModel):
    """One atomic eligibility assertion. Maps 1:1 onto a trial_eligibility_criteria row."""

    criterion_type: Literal["inclusion", "exclusion"]
    # Verbatim text of the single assertion — NOT the whole source bullet. One compound
    # bullet ("Stage IV NSCLC with no prior therapy") yields several of these.
    text: str
    category: CriterionCategory
    # Free-text refinement: required when category is OTHER; optional detail elsewhere.
    subtype: Optional[str] = None
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
- confidence in [0,1] reflects how cleanly the assertion classified."""


def eligibility_source_hash(text: str) -> str:
    """SHA-256 of the raw eligibility blob — gate re-extraction on this (skip if unchanged)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    """
    return [
        {
            "nct_id": nct_id,
            "criterion_type": item.criterion_type,
            "text": item.text,
            "category": item.category.value,
            "subtype": item.subtype,
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

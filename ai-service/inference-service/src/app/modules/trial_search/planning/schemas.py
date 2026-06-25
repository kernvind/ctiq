from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class Field(StrEnum):
    TITLE = "title"
    SUMMARY = "summary"
    ELIGIBILITY = "eligibility"
    OUTCOME = "outcome"
    INTERVENTION = "intervention"


class Intent(StrEnum):
    PATIENT = "patient"
    DESCRIPTIVE = "descriptive"
    # Analyst/competitor intent — "what is sponsor X doing", landscape questions. The
    # LLM planner classifies these; the rule-based planner never emits it.
    COMPETITIVE_INTEL = "competitive_intel"


# Single source of truth: which fields to search per intent.
INTENT_TO_FIELDS: dict[Intent, tuple[Field, ...]] = {
    Intent.PATIENT:     (Field.ELIGIBILITY, Field.SUMMARY),
    Intent.DESCRIPTIVE: (Field.SUMMARY, Field.TITLE, Field.INTERVENTION),
    # Landscape questions read like descriptive search over the same fields; the
    # distinguishing power is in the structured filters (sponsor/phase/status).
    Intent.COMPETITIVE_INTEL: (Field.SUMMARY, Field.TITLE, Field.INTERVENTION),
}


# Phrases that strongly suggest a patient describing themselves,
# regardless of position in the query.
ANYWHERE_PATIENT_PHRASES: tuple[str, ...] = (
    "diagnosed with", "history of", "previously treated",
    "after taking", "living with", "suffering from",
    "struggling with", "dealing with", "affected by",
    "battling", "coping with", "family history of",
    "symptoms of", "experience with",
)

# Phrases that signal patient context ONLY when the query starts with them.
# Substring matching here causes false positives ("trials in my area").
PREFIX_PATIENT_PHRASES: tuple[str, ...] = (
    "i have", "i am", "i'm", "my ",
    "stage ", "prior ",
)


# Map common phrasings -> CT.gov phase enum value(s).
# Combo values are tuples so the SQL filter handles them with IN UNNEST.
PHASE_PATTERNS: dict[str, tuple[str, ...]] = {
    "early phase 1":   ("EARLY_PHASE1",),
    "phase 0":         ("EARLY_PHASE1",),
    "phase 1":         ("PHASE1",),
    "phase i":         ("PHASE1",),
    "phase 1/2":       ("PHASE1", "PHASE2"),
    "phase i/ii":      ("PHASE1", "PHASE2"),
    "phase 1/phase 2": ("PHASE1", "PHASE2"),
    "phase 2":         ("PHASE2",),
    "phase ii":        ("PHASE2",),
    "phase 2/3":       ("PHASE2", "PHASE3"),
    "phase ii/iii":    ("PHASE2", "PHASE3"),
    "phase 2/phase 3": ("PHASE2", "PHASE3"),
    "phase 3":         ("PHASE3",),
    "phase iii":       ("PHASE3",),
    "phase 4":         ("PHASE4",),
    "phase iv":        ("PHASE4",),
    "post-market":     ("PHASE4",),
    "postmarket":      ("PHASE4",),
    "not applicable":  ("NA",),
}

# Pre-sort longest first so combos match before their substrings.
PHASE_PATTERNS_SORTED: list[tuple[str, tuple[str, ...]]] = sorted(
    PHASE_PATTERNS.items(),
    key=lambda kv: -len(kv[0]),
)


# CT.gov recruitment-status enums the LLM is told to emit. Used to validate/canonicalize
# the model's `statuses` before they hit the SQL filter — unknown values are dropped.
VALID_STATUSES: frozenset[str] = frozenset(
    {
        "RECRUITING",
        "NOT_YET_RECRUITING",
        "ENROLLING_BY_INVITATION",
        "ACTIVE_NOT_RECRUITING",
        "COMPLETED",
        "TERMINATED",
        "WITHDRAWN",
        "SUSPENDED",
    }
)


@dataclass(frozen=True)
class QueryPlan:
    intent: Intent
    fields: tuple[Field, ...]
    phase_filter: Optional[tuple[str, ...]] = None
    top_k: int = 20
    # Slice 3 structured pre-filters. None = no filter on that dimension. Only the LLM
    # planner populates these; the rule-based planner leaves them None.
    status_filter: Optional[tuple[str, ...]] = None
    sponsor_filter: Optional[str] = None
    condition_filter: Optional[tuple[str, ...]] = None
    # The filter-stripped conceptual core to embed for vector search. None = embed the raw
    # query (rule-based planner, or LLM returning an empty core).
    semantic_query: Optional[str] = None
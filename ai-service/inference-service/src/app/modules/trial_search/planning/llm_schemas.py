from typing import Literal, Optional

from pydantic import BaseModel


class CompiledQuery(BaseModel):
    """A user's natural-language trial search, compiled by the LLM planner into a
    structured query.

    `semantic_query` feeds vector search; the rest are structured pre-filters. This is the
    agent-ready contract: today only `intent` + `phases` shape the QueryPlan, but the LLM
    already extracts `statuses` / `sponsor` / `conditions` so wiring them into the
    repository's SQL pre-filters is additive (no prompt or schema change needed then).
    """

    # patient = user describing themselves seeking a trial; competitive_intel = analyst
    # asking about a sponsor's pipeline / the landscape; descriptive = everything else.
    intent: Literal["patient", "descriptive", "competitive_intel"]

    # The conceptual core for semantic/vector search, with structured filters stripped out.
    semantic_query: str

    # ClinicalTrials.gov phase enums (EARLY_PHASE1/PHASE1/PHASE2/PHASE3/PHASE4/NA). Empty
    # = no phase filter.
    phases: list[str]

    # Recruitment-status enums (RECRUITING, COMPLETED, ...). Empty = no status filter.
    statuses: list[str]

    # A lead sponsor / company name if the user named one (e.g. "Pfizer"), else null.
    sponsor: Optional[str]

    # Condition / disease terms (e.g. ["melanoma"]). Empty = none.
    conditions: list[str]

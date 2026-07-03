from typing import Literal, Optional

from pydantic import BaseModel


class CompiledQuery(BaseModel):
    """A user's natural-language trial search, compiled by the LLM planner into a
    structured query.

    `semantic_query` feeds vector search; the rest are structured pre-filters. The planner
    maps all of these onto the `QueryPlan`, and the repository applies them as SQL pre-filters
    (status `IN`, phase array-overlap, sponsor/condition `ILIKE`) — see
    `repository.vector_search`. `semantic_query` is embedded in place of the raw query so
    filter words don't pollute the vector match.
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

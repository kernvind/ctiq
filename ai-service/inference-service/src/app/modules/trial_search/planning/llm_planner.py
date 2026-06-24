import logging
from typing import Optional

from openai import AsyncOpenAI

from src.app.modules.trial_search.planning.llm_schemas import CompiledQuery
from src.app.modules.trial_search.planning.schemas import (
    INTENT_TO_FIELDS,
    Intent,
    QueryPlan,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You compile a user's natural-language clinical-trial search into a structured query for a \
search engine over public ClinicalTrials.gov data.

- semantic_query: the conceptual core of the request for semantic/vector search, with \
structured filters removed (e.g. "GLP-1 obesity trials").
- phases: ClinicalTrials.gov phase enums only - EARLY_PHASE1, PHASE1, PHASE2, PHASE3, \
PHASE4, NA. Empty if unspecified.
- statuses: recruitment-status enums - RECRUITING, NOT_YET_RECRUITING, \
ENROLLING_BY_INVITATION, ACTIVE_NOT_RECRUITING, COMPLETED, TERMINATED, WITHDRAWN, \
SUSPENDED. Empty if unspecified.
- sponsor: a lead sponsor / company name if the user names one (e.g. "Pfizer"), else null.
- conditions: condition or disease terms (e.g. ["melanoma"]). Empty if none.
- intent: "patient" if the user describes themselves or their condition seeking a trial; \
"competitive_intel" if they ask about a sponsor's pipeline or the competitive landscape; \
otherwise "descriptive".

You only translate the query. Never give medical advice, never invent trials, and never \
add filters the user did not imply. When unsure about a filter, leave it empty/null."""

# Map an alphanumerics-only, upper-cased phase token -> canonical CT.gov enum. Lets the
# model emit "Phase 3", "PHASE_3", or "phase iii"-style values and still land on PHASE3.
_PHASE_CANON: dict[str, str] = {
    "EARLYPHASE1": "EARLY_PHASE1",
    "PHASE0": "EARLY_PHASE1",
    "PHASE1": "PHASE1",
    "PHASE2": "PHASE2",
    "PHASE3": "PHASE3",
    "PHASE4": "PHASE4",
    "NA": "NA",
    "NOTAPPLICABLE": "NA",
}

_DEFAULT_TOP_K = 20


def _normalize_phases(phases: list[str]) -> tuple[str, ...]:
    """Coerce the model's phase strings to canonical CT.gov enums; drop anything unknown."""
    out: list[str] = []
    for raw in phases:
        token = "".join(c for c in raw.upper() if c.isalnum())
        canon = _PHASE_CANON.get(token)
        if canon and canon not in out:
            out.append(canon)
    return tuple(out)


class LLMQueryPlanner:
    """NL->structured-query planner backed by an LLM (OpenAI structured outputs).

    Produces the same ``QueryPlan`` shape as the rule-based planner, so it drops into the
    existing search path. The richer filters the LLM extracts (statuses/sponsor/
    conditions) are carried on ``CompiledQuery`` and wired into the repository pre-filters
    in a follow-up; today only ``intent`` + ``phases`` shape the plan.

    The OpenAI client is injected (not constructed here) so the provider stays a swappable
    detail and the planner is unit-testable without network access.
    """

    def __init__(self, client: AsyncOpenAI, model: str):
        self._client = client
        self._model = model

    async def compile(self, query: str) -> Optional[CompiledQuery]:
        """Call the LLM to compile a query. Returns None if the model refuses/declines.

        Uses the OpenAI Responses API (`responses.parse`) — the current structured-output
        surface and the right path for the GPT-5 family. `instructions` carries the system
        prompt; `output_parsed` is the typed `CompiledQuery` (or None on refusal)."""
        response = await self._client.responses.parse(
            model=self._model,
            instructions=_SYSTEM_PROMPT,
            input=query,
            text_format=CompiledQuery,
        )
        return response.output_parsed

    async def plan(self, query: str) -> QueryPlan:
        compiled = await self.compile(query)
        if compiled is None:
            # Refusal / unparseable response — fail safe to a plain descriptive search.
            logger.warning("LLM planner: no parsed query; falling back to DESCRIPTIVE")
            return QueryPlan(
                intent=Intent.DESCRIPTIVE,
                fields=INTENT_TO_FIELDS[Intent.DESCRIPTIVE],
                top_k=_DEFAULT_TOP_K,
            )

        try:
            intent = Intent(compiled.intent)
        except ValueError:
            intent = Intent.DESCRIPTIVE

        phase_filter = _normalize_phases(compiled.phases) or None
        return QueryPlan(
            intent=intent,
            fields=INTENT_TO_FIELDS[intent],
            phase_filter=phase_filter,
            top_k=_DEFAULT_TOP_K,
        )

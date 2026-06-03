import re
from typing import Optional

from src.app.modules.trial_search.planning.schemas import (
    Field,
    Intent,
    QueryPlan,
    INTENT_TO_FIELDS,
    ANYWHERE_PATIENT_PHRASES,
    PREFIX_PATIENT_PHRASES,
    PHASE_PATTERNS_SORTED,
)


class RuleBasedQueryPlanner:
    def plan(self, query: str) -> QueryPlan:
        normalized = query.lower()
        intent = self._classify_intent(normalized)
        return QueryPlan(
            intent=intent,
            fields=INTENT_TO_FIELDS[intent],
            phase_filter=self._extract_phase(normalized),
        )

    def _classify_intent(self, normalized: str) -> Intent:
        if any(phrase in normalized for phrase in ANYWHERE_PATIENT_PHRASES):
            return Intent.PATIENT
        if any(normalized.startswith(prefix) for prefix in PREFIX_PATIENT_PHRASES):
            return Intent.PATIENT
        return Intent.DESCRIPTIVE

    def _extract_phase(self, normalized: str) -> Optional[tuple[str, ...]]:
        for pattern, phases in PHASE_PATTERNS_SORTED:
            if re.search(rf"\b{re.escape(pattern)}\b", normalized):
                return phases
        return None
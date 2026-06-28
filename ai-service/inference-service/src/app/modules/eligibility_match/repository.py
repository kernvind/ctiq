import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ctiq_db import TrialEligibilityCriterion

logger = logging.getLogger(__name__)


class EligibilityMatchRepository:
    """Read-side repository for structured eligibility criteria (SQLAlchemy async ORM)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_criteria(self, nct_id: str) -> list[dict]:
        """Return a trial's eligibility criteria as plain dicts for the pure evaluator
        (criterion_type, category, text, predicate, is_actionable), in display order."""
        rows = await self.session.scalars(
            select(TrialEligibilityCriterion)
            .where(TrialEligibilityCriterion.nct_id == nct_id)
            .order_by(TrialEligibilityCriterion.display_order)
        )
        return [
            {
                "criterion_type": r.criterion_type,
                "category": r.category,
                "text": r.text,
                "predicate": r.predicate,
                "is_actionable": r.is_actionable,
            }
            for r in rows
        ]

    async def get_criteria_bulk(self, nct_ids: list[str]) -> dict[str, list[dict]]:
        """Load criteria for many trials in one query → {nct_id: [criterion dicts]} (patient-
        first batch match). nct_ids absent from the result simply have no extracted criteria."""
        if not nct_ids:
            return {}
        rows = await self.session.scalars(
            select(TrialEligibilityCriterion)
            .where(TrialEligibilityCriterion.nct_id.in_(nct_ids))
            .order_by(TrialEligibilityCriterion.nct_id, TrialEligibilityCriterion.display_order)
        )
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r.nct_id, []).append(
                {
                    "criterion_type": r.criterion_type,
                    "category": r.category,
                    "text": r.text,
                    "predicate": r.predicate,
                    "is_actionable": r.is_actionable,
                }
            )
        return grouped

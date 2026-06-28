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

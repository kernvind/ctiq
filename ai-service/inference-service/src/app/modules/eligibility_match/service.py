import logging
from typing import Optional

from src.app.modules.eligibility_match.evaluator import match_criteria
from src.app.modules.eligibility_match.repository import EligibilityMatchRepository
from src.app.modules.eligibility_match.schemas import MatchResult, PatientProfile

logger = logging.getLogger(__name__)


class EligibilityMatchService:
    """Stateless patient↔trial eligibility match over structured predicates (ROADMAP step 6).

    Loads a trial's criteria and evaluates them against the supplied profile. The profile is
    never persisted — matching is purely in-request (the PHI gate). Returns None when the
    trial has no extracted criteria yet (Stage A hasn't run for it).
    """

    def __init__(self, repository: EligibilityMatchRepository):
        self.repository = repository

    async def match(self, nct_id: str, profile: PatientProfile) -> Optional[MatchResult]:
        nct_id = nct_id.strip().upper()
        criteria = await self.repository.get_criteria(nct_id)
        if not criteria:
            logger.info("No eligibility criteria for %s — cannot match", nct_id)
            return None
        result = match_criteria(nct_id, criteria, profile)
        logger.info(
            "Match %s: signal=%s pass=%d fail=%d uncertain=%d",
            nct_id, result.signal.value, result.n_pass, result.n_fail, result.n_uncertain,
        )
        return result

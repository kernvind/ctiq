import asyncio

from src.app.modules.eligibility_match.service import PatientMatchService
from src.app.modules.eligibility_match.schemas import PatientProfile, TrialSignal


class _StubSearchRepo:
    """Returns candidate display metadata for the requested nct_ids (portfolio path)."""

    def __init__(self, meta_by_nct):
        self._meta = meta_by_nct

    async def get_trials_meta(self, nct_ids):
        return [self._meta[n] for n in nct_ids if n in self._meta]


class _StubMatchRepo:
    def __init__(self, criteria_by_nct):
        self._criteria = criteria_by_nct

    async def get_criteria_bulk(self, nct_ids):
        return {n: self._criteria[n] for n in nct_ids if n in self._criteria}


def _service(meta, criteria):
    # embedder is unused on the portfolio path (no vector search), so None is fine.
    return PatientMatchService(_StubSearchRepo(meta), _StubMatchRepo(criteria), embedder=None)


def test_screen_portfolio_empty_returns_empty():
    svc = _service({}, {})
    assert asyncio.run(svc.screen_portfolio(PatientProfile(), [])) == []


def test_screen_portfolio_ranks_and_flags_missing_criteria():
    meta = {
        "NCT-FIT": {"nct_id": "NCT-FIT", "brief_title": "A", "overall_status": "RECRUITING",
                    "phases": ["PHASE2"], "conditions": ["melanoma"], "lead_sponsor_name": "X"},
        "NCT-NOCRIT": {"nct_id": "NCT-NOCRIT", "brief_title": "B", "overall_status": "RECRUITING",
                       "phases": [], "conditions": [], "lead_sponsor_name": None},
    }
    criteria = {
        "NCT-FIT": [
            {"criterion_type": "inclusion", "category": "performance_status", "text": "ECOG 0-1",
             "predicate": {"scale": "ECOG", "min": 0, "max": 1}, "is_actionable": True},
        ],
        # NCT-NOCRIT: no extracted criteria
    }
    svc = _service(meta, criteria)

    ranked = asyncio.run(svc.screen_portfolio(PatientProfile(ecog=1), ["NCT-FIT", "NCT-NOCRIT"]))
    by_nct = {m.nct_id: m for m in ranked}

    assert by_nct["NCT-FIT"].signal is TrialSignal.LIKELY_ELIGIBLE
    assert by_nct["NCT-FIT"].has_criteria is True
    # A portfolio trial with no extracted eligibility surfaces as "criteria not available".
    assert by_nct["NCT-NOCRIT"].has_criteria is False

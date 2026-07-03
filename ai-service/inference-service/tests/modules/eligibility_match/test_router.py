import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.app.api.dependencies import (
    get_eligibility_match_service,
    get_patient_match_service,
)
from src.app.api.security import verify_internal_token
from src.app.core.config import Settings, get_settings
from src.app.modules.eligibility_match.router import router as match_router
from src.app.modules.eligibility_match.schemas import (
    MatchedTrial,
    MatchResult,
    TrialSignal,
)

BASE = "/api/v1/match/trials"
TOKEN = "s3cret"


class StubMatchService:
    """Per-trial EligibilityMatchService stub (no DB)."""

    def __init__(self, result=None):
        self._result = result

    async def match(self, nct_id: str, profile):
        return self._result


class StubPatientService:
    """Patient-first PatientMatchService stub (no DB/embedder)."""

    def __init__(self, results=None):
        self._results = results or []

    async def match_trials(self, request):
        return self._results

    async def screen_portfolio(self, profile, nct_ids):
        return self._results


def _client(match_result=None, patient_results=None) -> TestClient:
    app = FastAPI()
    app.include_router(match_router, dependencies=[Depends(verify_internal_token)])
    app.dependency_overrides[get_settings] = lambda: Settings(search_api_token=TOKEN)
    app.dependency_overrides[get_eligibility_match_service] = lambda: StubMatchService(match_result)
    app.dependency_overrides[get_patient_match_service] = lambda: StubPatientService(patient_results)
    return TestClient(app)


def _auth(headers=None):
    return {"X-Internal-Token": TOKEN, **(headers or {})}


# ── per-trial: POST /match/trials/{nct_id} ───────────────────────────────────
def test_per_trial_requires_internal_token():
    res = _client().post(f"{BASE}/NCT01234567", json={"ecog": 1})
    assert res.status_code == 401


def test_per_trial_rejects_malformed_nct_id():
    res = _client().post(f"{BASE}/not-an-nct", json={"ecog": 1}, headers=_auth())
    assert res.status_code == 422  # Path(pattern=...)


def test_per_trial_404_when_no_criteria():
    res = _client(match_result=None).post(f"{BASE}/NCT01234567", json={"ecog": 1}, headers=_auth())
    assert res.status_code == 404


def test_per_trial_returns_match_result():
    result = MatchResult(
        nct_id="NCT01234567", signal=TrialSignal.LIKELY_ELIGIBLE,
        n_pass=2, n_fail=0, n_uncertain=0, n_not_evaluated=1, verdicts=[],
    )
    res = _client(match_result=result).post(
        f"{BASE}/NCT01234567", json={"ecog": 1, "stage": "IV"}, headers=_auth()
    )
    assert res.status_code == 200
    body = res.json()
    assert body["nct_id"] == "NCT01234567"
    assert body["signal"] == "likely_eligible"


# ── patient-first: POST /match/trials ────────────────────────────────────────
def test_patient_first_requires_internal_token():
    res = _client().post(BASE, json={"condition": "melanoma", "profile": {}})
    assert res.status_code == 401


def test_patient_first_returns_ranked_list():
    ranked = [
        MatchedTrial(
            nct_id="NCT1", signal=TrialSignal.LIKELY_ELIGIBLE,
            n_pass=3, n_fail=0, n_uncertain=0, n_not_evaluated=0, has_criteria=True,
        )
    ]
    res = _client(patient_results=ranked).post(
        BASE, json={"condition": "melanoma", "profile": {"ecog": 1}}, headers=_auth()
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["nct_id"] == "NCT1" and body[0]["has_criteria"] is True


# ── portfolio screening: POST /match/portfolio ───────────────────────────────
def test_portfolio_requires_internal_token():
    res = _client().post("/api/v1/match/portfolio", json={"profile": {}, "nct_ids": []})
    assert res.status_code == 401


def test_portfolio_returns_ranked_list():
    ranked = [
        MatchedTrial(
            nct_id="NCT1", signal=TrialSignal.LIKELY_EXCLUDED,
            n_pass=1, n_fail=1, n_uncertain=0, n_not_evaluated=0, has_criteria=True,
        )
    ]
    res = _client(patient_results=ranked).post(
        "/api/v1/match/portfolio",
        json={"profile": {"ecog": 1}, "nct_ids": ["NCT1", "NCT2"]},
        headers=_auth(),
    )
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1 and body[0]["nct_id"] == "NCT1"

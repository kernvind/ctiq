import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.app.api.dependencies import get_trial_search_service
from src.app.api.security import verify_internal_token
from src.app.core.config import Settings, get_settings
from src.app.modules.trial_search.router import router as search_router

URL = "/api/v1/search/trials"
TOKEN = "s3cret"
VALID_QUERY = {"q": "melanoma immunotherapy trials"}  # >= 10 chars


class StubService:
    """Stands in for TrialSearchService so the route can be exercised without a model/DB."""

    def __init__(self, detail=None):
        self._detail = detail

    async def search_trials(self, query: str):
        return []

    async def get_trial(self, nct_id: str):
        return self._detail


@pytest.fixture
def client() -> TestClient:
    # Minimal app: just the search router behind the token gate, with the heavy
    # service + settings dependencies overridden. No lifespan, so no model/DB load.
    app = FastAPI()
    app.include_router(search_router, dependencies=[Depends(verify_internal_token)])
    app.dependency_overrides[get_settings] = lambda: Settings(search_api_token=TOKEN)
    app.dependency_overrides[get_trial_search_service] = lambda: StubService()
    return TestClient(app)


def test_rejects_request_without_the_internal_token(client: TestClient):
    res = client.get(URL, params=VALID_QUERY)
    assert res.status_code == 401


def test_rejects_a_wrong_internal_token(client: TestClient):
    res = client.get(URL, params=VALID_QUERY, headers={"X-Internal-Token": "wrong"})
    assert res.status_code == 401


def test_allows_request_with_a_valid_internal_token(client: TestClient):
    res = client.get(URL, params=VALID_QUERY, headers={"X-Internal-Token": TOKEN})
    assert res.status_code == 200
    assert res.json() == []


def test_validates_query_length_even_when_authorized(client: TestClient):
    res = client.get(URL, params={"q": "short"}, headers={"X-Internal-Token": TOKEN})
    assert res.status_code == 422  # Query(min_length=10)


# ── trial detail (GET /trials/{nct_id}) ─────────────────────────────────────────


def _client_with_detail(detail) -> TestClient:
    app = FastAPI()
    app.include_router(search_router, dependencies=[Depends(verify_internal_token)])
    app.dependency_overrides[get_settings] = lambda: Settings(search_api_token=TOKEN)
    app.dependency_overrides[get_trial_search_service] = lambda: StubService(detail=detail)
    return TestClient(app)


def test_detail_requires_the_internal_token():
    res = _client_with_detail(None).get(f"{URL}/NCT01234567")
    assert res.status_code == 401


def test_detail_returns_404_when_service_finds_nothing():
    res = _client_with_detail(None).get(
        f"{URL}/NCT01234567", headers={"X-Internal-Token": TOKEN}
    )
    assert res.status_code == 404


def test_detail_rejects_a_malformed_nct_id():
    res = _client_with_detail(None).get(
        f"{URL}/not-an-nct-id", headers={"X-Internal-Token": TOKEN}
    )
    assert res.status_code == 422  # Path(pattern=...)


def test_detail_returns_the_trial_when_found():
    from src.app.modules.trial_search.schemas import TrialDetail

    detail = TrialDetail(nct_id="NCT01234567", brief_title="A study")
    res = _client_with_detail(detail).get(
        f"{URL}/NCT01234567", headers={"X-Internal-Token": TOKEN}
    )
    assert res.status_code == 200
    assert res.json()["nct_id"] == "NCT01234567"
    assert res.json()["brief_title"] == "A study"

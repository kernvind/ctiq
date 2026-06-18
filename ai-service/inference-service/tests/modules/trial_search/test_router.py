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

    async def search_trials(self, query: str):
        return []


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

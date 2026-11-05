import json
import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from src.app.infra.observability.middleware import ObservabilityMiddleware


def _sample(name: str, **labels) -> float:
    return REGISTRY.get_sample_value(name, labels) or 0.0


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/")
    def health():
        return {"status": "ok"}

    @app.get("/items/{item_id}")
    def item(item_id: str):
        return {"id": item_id}

    @app.get("/search")
    def search(q: str):
        return {"ok": True}

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="nope")

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    return TestClient(app, raise_server_exceptions=False)


def test_route_template_is_the_metric_label_not_the_raw_path(client):
    before = _sample(
        "http_requests_total", method="GET", route="/items/{item_id}", status="200"
    )

    client.get("/items/abc")
    client.get("/items/def")

    after = _sample(
        "http_requests_total", method="GET", route="/items/{item_id}", status="200"
    )
    assert after - before == 2
    assert _sample("http_requests_total", method="GET", route="/items/abc", status="200") == 0


def test_latency_histogram_is_recorded(client):
    before = _sample(
        "http_request_duration_seconds_count", method="GET", route="/items/{item_id}"
    )
    client.get("/items/abc")
    after = _sample(
        "http_request_duration_seconds_count", method="GET", route="/items/{item_id}"
    )
    assert after - before == 1


def test_unmatched_paths_collapse_into_one_label(client):
    before = _sample("http_requests_total", method="GET", route="unmatched", status="404")
    client.get("/scan/one")
    client.get("/scan/two")
    after = _sample("http_requests_total", method="GET", route="unmatched", status="404")
    assert after - before == 2


def test_handled_and_unhandled_errors_are_counted_with_their_status(client):
    b404 = _sample("http_requests_total", method="GET", route="/missing", status="404")
    b500 = _sample("http_requests_total", method="GET", route="/boom", status="500")

    assert client.get("/missing").status_code == 404
    assert client.get("/boom").status_code == 500

    assert _sample("http_requests_total", method="GET", route="/missing", status="404") - b404 == 1
    assert _sample("http_requests_total", method="GET", route="/boom", status="500") - b500 == 1


def test_in_progress_gauge_returns_to_zero_even_after_an_exception(client):
    client.get("/boom")
    assert _sample("http_requests_in_progress") == 0


def test_health_probe_is_neither_counted_nor_logged(client, caplog):
    caplog.set_level(logging.DEBUG, logger="app.access")
    before = _sample("http_requests_total", method="GET", route="/", status="200")

    assert client.get("/").status_code == 200

    assert _sample("http_requests_total", method="GET", route="/", status="200") == before
    assert not [r for r in caplog.records if r.name == "app.access"]


def test_generates_a_request_id_and_returns_it(client):
    response = client.get("/items/abc")
    assert len(response.headers["x-request-id"]) == 32


def test_accepts_a_safe_caller_supplied_request_id(client):
    response = client.get("/items/abc", headers={"X-Request-ID": "api-core-7f3a"})
    assert response.headers["x-request-id"] == "api-core-7f3a"


def test_rejects_an_unsafe_request_id(client):
    response = client.get("/items/abc", headers={"X-Request-ID": 'x"; DROP TABLE'})
    assert response.headers["x-request-id"] != 'x"; DROP TABLE'
    assert len(response.headers["x-request-id"]) == 32


def test_access_log_never_contains_the_query_string(client, caplog):
    caplog.set_level(logging.INFO, logger="app.access")

    client.get("/search?q=45 year old woman with melanoma in Fresno")

    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    rendered = json.dumps(records[0].__dict__, default=str)
    assert "melanoma" not in rendered and "Fresno" not in rendered
    assert records[0].http_path == "/search"
    assert records[0].http_status == 200


def test_access_log_level_follows_status(client, caplog):
    caplog.set_level(logging.INFO, logger="app.access")

    client.get("/items/a")
    client.get("/missing")
    client.get("/boom")

    levels = [r.levelno for r in caplog.records if r.name == "app.access"]
    assert levels == [logging.INFO, logging.WARNING, logging.ERROR]

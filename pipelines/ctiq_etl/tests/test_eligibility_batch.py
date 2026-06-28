from datetime import date

from src.config import settings
from src.tasks.transform.eligibility_batch import (
    _iter_request_groups,
    _meta,
    _output_text,
    build_requests,
)


# ── _meta: normalize request_hashes value (backward-compatible) ───────────────
def test_meta_rich_dict_with_iso_date():
    assert _meta({"h": "abc", "lupd": "2024-01-15"}) == ("abc", date(2024, 1, 15))


def test_meta_rich_dict_with_none_lupd():
    assert _meta({"h": "abc", "lupd": None}) == ("abc", None)


def test_meta_legacy_bare_hash_string():
    assert _meta("abc") == ("abc", None)


def test_meta_unknown_or_bad_date():
    assert _meta(None) == (None, None)
    assert _meta({"h": "abc", "lupd": "not-a-date"}) == ("abc", None)


# ── build_requests: one line per trial, custom_id carries nct_id ──────────────
def test_build_requests_shape():
    pending = {"NCT1": ("Inclusion: adults", "h1")}
    reqs = build_requests(pending, model="gpt-5-mini")
    assert len(reqs) == 1
    r = reqs[0]
    assert r["custom_id"] == "NCT1"
    assert r["url"] == "/v1/responses"
    assert set(r["body"]) == {"model", "instructions", "input", "text"}
    assert r["body"]["model"] == "gpt-5-mini"
    assert r["body"]["input"] == "Inclusion: adults"
    assert "format" in r["body"]["text"]  # strict structured-output config


# ── _iter_request_groups: split at the per-batch cap ──────────────────────────
def test_iter_request_groups_splits_at_cap(monkeypatch):
    monkeypatch.setattr(settings, "eligibility_batch_max_requests", 2)
    pending = {f"NCT{i}": ("t", "h") for i in range(5)}
    groups = list(_iter_request_groups(pending))
    assert [len(g) for g, _ in groups] == [2, 2, 1]
    assert sum(len(reqs) for _, reqs in groups) == 5


# ── _output_text: tolerant extraction from the Responses envelope ─────────────
def test_output_text_convenience_field():
    assert _output_text({"output_text": "hello"}) == "hello"


def test_output_text_digs_into_output_content():
    body = {"output": [{"content": [{"type": "output_text", "text": "dug"}]}]}
    assert _output_text(body) == "dug"


def test_output_text_none_when_absent_or_bad():
    assert _output_text({}) is None
    assert _output_text("nope") is None

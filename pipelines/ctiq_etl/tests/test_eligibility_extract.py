import hashlib
from datetime import date
from types import SimpleNamespace

from src.tasks.transform.eligibility_extract import (
    CriterionCategory,
    EligibilityExtractor,
    ExtractedCriterion,
    ExtractedEligibility,
    Predicate,
    _no_nul,
    collect_pending,
    eligibility_source_hash,
    lupd_map,
    to_db_rows,
)


def _crit(**over) -> ExtractedCriterion:
    base = dict(
        criterion_type="inclusion", text="t", category=CriterionCategory.BIOMARKER,
        confidence=0.9, is_actionable=True, source_bullet_index=0,
    )
    base.update(over)
    return ExtractedCriterion(**base)


# ── _no_nul: recursive NUL strip (regression for the JSONB/text NUL bugs) ──────
def test_no_nul_strips_from_string():
    assert _no_nul("EGFR\x00 mut") == "EGFR mut"


def test_no_nul_recurses_into_dict_and_list():
    out = _no_nul({"unit": "kg/m\x002", "tags": ["a\x00", "b"]})
    assert out == {"unit": "kg/m2", "tags": ["a", "b"]}


def test_no_nul_passes_non_strings_through():
    assert _no_nul(5) == 5 and _no_nul(None) is None and _no_nul(True) is True


# ── eligibility_source_hash: version-salted (forces re-extract on bump) ────────
def test_source_hash_is_salted_not_plain_sha256():
    assert eligibility_source_hash("x") != hashlib.sha256(b"x").hexdigest()


def test_source_hash_is_deterministic():
    assert eligibility_source_hash("abc") == eligibility_source_hash("abc")


# ── to_db_rows: predicate dump, NUL strip, provenance, ordering ───────────────
def test_to_db_rows_dumps_predicate_dropping_nulls():
    items = [_crit(predicate=Predicate(marker="EGFR", relation="excluded"))]
    row = to_db_rows("NCT1", items, source_hash="h", ingestion_date=date(2026, 6, 24))[0]
    assert row["predicate"] == {"marker": "EGFR", "relation": "excluded"}  # None fields gone


def test_to_db_rows_serializes_washout_days_predicate():
    # ROADMAP 6b: a prior_therapy washout window survives the predicate → JSONB round-trip.
    items = [_crit(predicate=Predicate(therapy_class="chemotherapy", relation="prohibited",
                                       washout_days=21))]
    row = to_db_rows("NCT1", items, source_hash="h", ingestion_date=date(2026, 6, 24))[0]
    assert row["predicate"] == {
        "therapy_class": "chemotherapy", "relation": "prohibited", "washout_days": 21,
    }


def test_to_db_rows_strips_nul_inside_predicate_and_text():
    items = [_crit(text="a\x00b", predicate=Predicate(analyte="kg/m\x002", op=">=", value=1))]
    row = to_db_rows("NCT1", items, source_hash="h", ingestion_date=date(2026, 6, 24))[0]
    assert row["text"] == "ab"
    assert row["predicate"]["analyte"] == "kg/m2"


def test_to_db_rows_null_predicate_and_provenance_and_order():
    items = [_crit(predicate=None), _crit(predicate=None)]
    rows = to_db_rows(
        "NCT1", items, source_hash="h", ingestion_date=date(2026, 6, 24),
        last_update_post_date=date(2024, 1, 15),
    )
    assert rows[0]["predicate"] is None
    assert [r["display_order"] for r in rows] == [0, 1]
    assert rows[0]["last_update_post_date"] == date(2024, 1, 15)
    assert rows[0]["category"] == "biomarker"


# ── collect_pending: indexing + hash gate ────────────────────────────────────
def _study(nct_id, text):
    return {"trial": {"nct_id": nct_id, "eligibility_criteria": text}}


def test_collect_pending_skips_empty_and_missing():
    studies = [
        _study("NCT1", "Inclusion: adults"),
        _study("NCT2", "   "),            # blank → skipped
        {"trial": {"eligibility_criteria": "x"}},  # no nct_id → skipped
        None,
    ]
    pending = collect_pending(studies, skip_existing_check=True)
    assert list(pending) == ["NCT1"]


def test_collect_pending_gate_skips_unchanged(monkeypatch):
    studies = [_study("NCT1", "txt"), _study("NCT2", "txt2")]
    h1 = eligibility_source_hash("txt")
    # NCT1 already extracted with the same hash → skipped; NCT2 changed → kept.
    monkeypatch.setattr(
        "src.tasks.load.bq.get_existing_eligibility_hash",
        lambda nct_ids: {"NCT1": h1, "NCT2": "stale"},
    )
    pending = collect_pending(studies, skip_existing_check=False)
    assert list(pending) == ["NCT2"]


# ── lupd_map ──────────────────────────────────────────────────────────────────
def test_lupd_map():
    studies = [
        {"trial": {"nct_id": "NCT1", "last_update_post_date": date(2024, 1, 1)}},
        {"trial": {"nct_id": "NCT2"}},
        None,
    ]
    m = lupd_map(studies)
    assert m == {"NCT1": date(2024, 1, 1), "NCT2": None}


# ── EligibilityExtractor.extract: fail-soft ──────────────────────────────────
def _extractor(parse_impl):
    client = SimpleNamespace(responses=SimpleNamespace(parse=parse_impl))
    return EligibilityExtractor(client, model="gpt-5-mini")


def test_extract_empty_text_returns_empty():
    assert _extractor(lambda **kw: None).extract("   ") == []


def test_extract_returns_parsed_criteria():
    parsed = ExtractedEligibility(criteria=[_crit(text="Stage IV")])
    items = _extractor(lambda **kw: SimpleNamespace(output_parsed=parsed)).extract("text")
    assert len(items) == 1 and items[0].text == "Stage IV"


def test_extract_failsoft_on_exception():
    def boom(**kw):
        raise RuntimeError("api down")
    assert _extractor(boom).extract("text") == []  # never raises into the ETL


# ── strict structured-output schema safety (regression for the silent-zero bug) ──
def test_confidence_is_clamped_into_unit_interval():
    # A model-returned value outside [0, 1] is corrected, not rejected (would lose the trial).
    assert _crit(confidence=5.0).confidence == 1.0
    assert _crit(confidence=-0.2).confidence == 0.0
    assert _crit(confidence=0.7).confidence == 0.7


def test_strict_schema_has_no_numeric_bounds():
    # OpenAI strict structured outputs reject `minimum`/`maximum`; if a Field(ge/le) ever
    # re-introduces them, every extract call 400s and fail-softs to zero criteria. Guard the
    # exact schema the SDK sends (reuse the SDK converter the batch path also uses).
    from openai.lib._pydantic import to_strict_json_schema

    def _walk(node):
        if isinstance(node, dict):
            assert "minimum" not in node and "maximum" not in node, node
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(to_strict_json_schema(ExtractedEligibility))

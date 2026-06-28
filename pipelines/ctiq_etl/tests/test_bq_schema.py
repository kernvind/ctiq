"""Tests for the pyarrow → BigQuery schema converter (bq.ensure_curated_table backbone)."""
from src.tasks.load.bq import _bq_schema_from_arrow
from src.tasks.load.studies_to_parquet import SUBDIR_SCHEMAS


def _by_name(fields):
    return {f.name: f for f in fields}


def test_eligibility_schema_required_vs_nullable():
    fields = _by_name(_bq_schema_from_arrow(SUBDIR_SCHEMAS["eligibility_criteria"]))
    # non-nullable parquet fields → REQUIRED
    for name in ("nct_id", "criterion_type", "text", "ingestion_date"):
        assert fields[name].mode == "REQUIRED", name
    # the rest → NULLABLE
    for name in ("category", "subtype", "confidence", "is_actionable", "source_hash"):
        assert fields[name].mode == "NULLABLE", name


def test_eligibility_schema_types():
    fields = _by_name(_bq_schema_from_arrow(SUBDIR_SCHEMAS["eligibility_criteria"]))
    assert fields["nct_id"].field_type == "STRING"
    assert fields["confidence"].field_type == "FLOAT64"
    assert fields["is_actionable"].field_type == "BOOL"
    assert fields["source_bullet_index"].field_type == "INT64"
    assert fields["ingestion_date"].field_type == "DATE"


def test_list_scalar_becomes_repeated():
    # embeddings.embedding is list<float64> → REPEATED FLOAT64
    fields = _by_name(_bq_schema_from_arrow(SUBDIR_SCHEMAS["embeddings"]))
    assert fields["embedding"].mode == "REPEATED"
    assert fields["embedding"].field_type == "FLOAT64"


def test_nested_struct_list_becomes_repeated_record():
    # locations.contacts is list<struct> → REPEATED RECORD with subfields
    fields = _by_name(_bq_schema_from_arrow(SUBDIR_SCHEMAS["locations"]))
    contacts = fields["contacts"]
    assert contacts.field_type == "RECORD"
    assert contacts.mode == "REPEATED"
    assert len(contacts.fields) > 0


def test_string_list_becomes_repeated_string():
    # trial.phases is list<string> → REPEATED STRING
    fields = _by_name(_bq_schema_from_arrow(SUBDIR_SCHEMAS["trial"]))
    assert fields["phases"].mode == "REPEATED"
    assert fields["phases"].field_type == "STRING"

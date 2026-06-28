"""Tests for eligibility_item_chunks — the Stage A rows → per-item embedding chunks.

NB: importing embed.py loads sentence-transformers/torch (module-level), so this file is
heavier than the others; the function under test is pure.
"""
from src.tasks.transform.embed import eligibility_item_chunks


def _row(**over):
    base = dict(
        nct_id="NCT1", criterion_type="inclusion", text="EGFR exon 19 deletion",
        is_actionable=True, display_order=0,
    )
    base.update(over)
    return base


def test_inclusion_and_exclusion_get_distinct_field_types():
    chunks = eligibility_item_chunks([
        _row(criterion_type="inclusion", display_order=0),
        _row(criterion_type="exclusion", text="prior anti-PD-1", display_order=1),
    ])
    fts = {c.field_type for c in chunks}
    assert fts == {"eligibility_inclusion", "eligibility_exclusion"}


def test_chunk_id_equals_display_order():
    chunks = eligibility_item_chunks([_row(display_order=7)])
    assert chunks[0].chunk_id == 7  # links the vector back to its criterion row


def test_boilerplate_and_blank_dropped():
    chunks = eligibility_item_chunks([
        _row(is_actionable=False, text="Other criteria apply", display_order=0),
        _row(text="   ", display_order=1),
        _row(text="real", display_order=2),
    ])
    assert [c.chunk_text for c in chunks] == ["real"]


def test_unknown_criterion_type_dropped():
    chunks = eligibility_item_chunks([_row(criterion_type="weird")])
    assert chunks == []

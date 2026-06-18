from src.app.modules.trial_search.hydrater import to_card, _truncate
from src.app.modules.trial_search.schemas import MatchingChunk, TrialSearchResultRow


def make_row(**overrides) -> TrialSearchResultRow:
    chunk = MatchingChunk(field_type="summary", chunk_text="some chunk text", distance=0.12)
    data = dict(
        nct_id="NCT001",
        brief_title="A Study of X",
        overall_status="RECRUITING",
        phases=["PHASE2"],
        lead_sponsor_name="Acme Pharma",
        lead_sponsor_class="INDUSTRY",
        min_age_years=18.0,
        max_age_years=65.0,
        sex="ALL",
        healthy_volunteers=True,
        best_distance=0.12,
        best_chunk=chunk,
        top_chunks=[chunk],
        total_sites=5,
        recruiting_sites=3,
        sample_facilities=[],
    )
    data.update(overrides)
    return TrialSearchResultRow(**data)


class TestToCard:
    def test_maps_a_populated_row(self):
        card = to_card(make_row())
        assert card.nct_id == "NCT001"
        assert card.brief_title == "A Study of X"
        assert card.overall_status == "RECRUITING"
        assert card.phases == ("PHASE2",)  # list -> tuple
        assert card.best_matching_chunk.field_type == "summary"
        assert card.eligibility.sex == "ALL"
        assert card.eligibility.accepts_healthy_volunteers is True
        assert card.locations.total_sites == 5
        assert card.lead_sponsor_name == "Acme Pharma"

    def test_applies_fallback_defaults_for_missing_fields(self):
        card = to_card(
            make_row(
                brief_title=None,
                overall_status=None,
                lead_sponsor_name=None,
                lead_sponsor_class=None,
                sex=None,
                phases=[],
            )
        )
        assert card.brief_title == "(no title)"
        assert card.overall_status == "UNKNOWN"
        assert card.lead_sponsor_name == "(unknown sponsor)"
        assert card.lead_sponsor_class == "OTHER"
        assert card.eligibility.sex == "ALL"
        assert card.phases == ()

    def test_truncates_a_long_best_chunk(self):
        long_text = "word " * 200  # 1000 chars
        card = to_card(
            make_row(
                best_chunk=MatchingChunk(
                    field_type="summary", chunk_text=long_text, distance=0.1
                )
            )
        )
        assert len(card.best_matching_chunk.chunk_text) <= 251
        assert card.best_matching_chunk.chunk_text.endswith("…")


class TestTruncate:
    def test_leaves_short_text_unchanged(self):
        assert _truncate("short text", 250) == "short text"

    def test_leaves_text_at_the_limit_unchanged(self):
        text = "x" * 50
        assert _truncate(text, 50) == text

    def test_cuts_long_text_at_a_word_boundary_with_ellipsis(self):
        out = _truncate("word " * 100, 50)
        assert out.endswith("…")
        assert len(out) <= 51
        # cut on a word boundary -> no trailing partial word before the ellipsis
        assert not out[:-1].endswith(" ")

    def test_handles_empty_text(self):
        assert _truncate("", 250) == ""

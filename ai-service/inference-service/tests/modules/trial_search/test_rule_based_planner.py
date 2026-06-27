import pytest

from src.app.modules.trial_search.planning.rule_based_planner import (
    RuleBasedQueryPlanner,
)
from src.app.modules.trial_search.planning.schemas import (
    Field,
    Intent,
    INTENT_TO_FIELDS,
)

planner = RuleBasedQueryPlanner()


class TestIntentClassification:
    @pytest.mark.parametrize(
        "query",
        [
            "diagnosed with stage 4 melanoma",  # anywhere phrase
            "someone with a history of diabetes",  # anywhere phrase mid-string
            "i have lung cancer",  # prefix "i have"
            "i'm 45 and looking for trials",  # prefix "i'm"
            "my mother has alzheimer's",  # prefix "my "
            "stage 3 breast cancer options",  # prefix "stage "
        ],
    )
    def test_patient_intent(self, query: str):
        assert planner.plan(query).intent is Intent.PATIENT

    @pytest.mark.parametrize(
        "query",
        [
            "phase 3 oncology trials by sponsor",
            "immunotherapy trials for melanoma",
            "clinical trials in my area",  # "my " only mid-string -> NOT patient
            "compare dropout rates across sponsors",
        ],
    )
    def test_descriptive_intent(self, query: str):
        assert planner.plan(query).intent is Intent.DESCRIPTIVE

    def test_classification_is_case_insensitive(self):
        assert planner.plan("DIAGNOSED WITH breast cancer").intent is Intent.PATIENT


class TestFields:
    def test_patient_intent_searches_eligibility_and_summary(self):
        plan = planner.plan("i have melanoma")
        assert plan.fields == INTENT_TO_FIELDS[Intent.PATIENT]
        assert plan.fields == (Field.ELIGIBILITY_INCLUSION, Field.SUMMARY)

    def test_descriptive_intent_searches_summary_title_intervention(self):
        plan = planner.plan("immunotherapy trials")
        assert plan.fields == (Field.SUMMARY, Field.TITLE, Field.INTERVENTION)

    def test_default_top_k(self):
        assert planner.plan("immunotherapy trials").top_k == 20


class TestPhaseExtraction:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("phase 3 trials", ("PHASE3",)),
            ("looking for phase iii studies", ("PHASE3",)),
            ("phase 1 first in human", ("PHASE1",)),
            ("phase 1/2 combination", ("PHASE1", "PHASE2")),
            ("phase ii/iii trials", ("PHASE2", "PHASE3")),
            ("early phase 1 dose escalation", ("EARLY_PHASE1",)),
            ("post-market surveillance", ("PHASE4",)),
        ],
    )
    def test_extracts_phase(self, query: str, expected: tuple[str, ...]):
        assert planner.plan(query).phase_filter == expected

    @pytest.mark.parametrize(
        "query",
        [
            "immunotherapy trials",
            "phase 30 nonsense",  # word boundary: must NOT match "phase 3"
            "melanoma treatment options",
        ],
    )
    def test_no_phase_filter(self, query: str):
        assert planner.plan(query).phase_filter is None

    def test_combo_matches_before_its_substring(self):
        # "phase 2/3" must map to the combo, not just "phase 2".
        assert planner.plan("phase 2/3 oncology").phase_filter == ("PHASE2", "PHASE3")

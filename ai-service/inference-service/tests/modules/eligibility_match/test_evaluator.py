from src.app.modules.eligibility_match.evaluator import (
    evaluate_criterion,
    match_criteria,
    rank_matches,
)
from src.app.modules.eligibility_match.schemas import PatientProfile, TrialSignal, Verdict


def _crit(**over) -> dict:
    base = dict(criterion_type="inclusion", category="biomarker", text="t",
                is_actionable=True, predicate=None)
    base.update(over)
    return base


def _verdict(criterion, profile):
    return evaluate_criterion(criterion, profile).verdict


# ── performance_status ────────────────────────────────────────────────────────
def test_ecog_in_range_passes():
    c = _crit(category="performance_status", predicate={"scale": "ECOG", "min": 0, "max": 1})
    assert _verdict(c, PatientProfile(ecog=1)) is Verdict.PASS


def test_ecog_out_of_range_fails():
    c = _crit(category="performance_status", predicate={"scale": "ECOG", "min": 0, "max": 1})
    assert _verdict(c, PatientProfile(ecog=2)) is Verdict.FAIL


def test_ecog_missing_is_uncertain():
    c = _crit(category="performance_status", predicate={"scale": "ECOG", "min": 0, "max": 1})
    assert _verdict(c, PatientProfile()) is Verdict.UNCERTAIN


# ── disease_stage ─────────────────────────────────────────────────────────────
def test_stage_match_passes_inclusion():
    c = _crit(category="disease_stage", predicate={"stage": ["IV"]})
    assert _verdict(c, PatientProfile(stage="iv")) is Verdict.PASS  # case-insensitive


def test_stage_mismatch_fails_inclusion():
    c = _crit(category="disease_stage", predicate={"stage": ["IV"]})
    assert _verdict(c, PatientProfile(stage="II")) is Verdict.FAIL


# ── demographic ───────────────────────────────────────────────────────────────
def test_age_below_min_fails():
    c = _crit(category="demographic", predicate={"min": 18, "unit": "years"})
    assert _verdict(c, PatientProfile(age_years=12)) is Verdict.FAIL


# ── lab_value ─────────────────────────────────────────────────────────────────
def test_lab_threshold_pass_and_fail():
    c = _crit(category="lab_value", predicate={"analyte": "ANC", "op": ">=", "value": 1500})
    assert _verdict(c, PatientProfile(labs={"ANC": 1800})) is Verdict.PASS
    assert _verdict(c, PatientProfile(labs={"ANC": 1000})) is Verdict.FAIL
    assert _verdict(c, PatientProfile()) is Verdict.UNCERTAIN


# ── biomarker: numeric threshold ──────────────────────────────────────────────
def test_pdl1_threshold():
    c = _crit(category="biomarker",
              predicate={"marker": "PD-L1", "op": ">=", "value": 1, "relation": "required"})
    assert _verdict(c, PatientProfile(biomarkers={"PD-L1": 60})) is Verdict.PASS
    assert _verdict(c, PatientProfile(biomarkers={"PD-L1": 0})) is Verdict.FAIL


# ── biomarker: exclusion + unknown_status ─────────────────────────────────────
def test_egfr_exclusion_wildtype_passes():
    c = _crit(criterion_type="exclusion", category="biomarker",
              predicate={"marker": "EGFR", "qualifier": "sensitizing",
                         "relation": "excluded", "unknown_status": "excluded"})
    # wild-type → trait absent → exclusion not triggered → PASS
    assert _verdict(c, PatientProfile(biomarkers={"EGFR": "wild-type"})) is Verdict.PASS


def test_egfr_exclusion_mutated_fails():
    c = _crit(criterion_type="exclusion", category="biomarker",
              predicate={"marker": "EGFR", "relation": "excluded"})
    assert _verdict(c, PatientProfile(biomarkers={"EGFR": "L858R"})) is Verdict.FAIL  # named mutation = present


def test_egfr_unknown_status_excluded_forces_fail():
    c = _crit(criterion_type="exclusion", category="biomarker",
              predicate={"marker": "EGFR", "relation": "excluded", "unknown_status": "excluded"})
    # status missing + unknown_status=excluded → FAIL, not UNCERTAIN
    assert _verdict(c, PatientProfile()) is Verdict.FAIL


def test_egfr_unknown_without_override_is_uncertain():
    c = _crit(criterion_type="exclusion", category="biomarker",
              predicate={"marker": "EGFR", "relation": "excluded"})
    assert _verdict(c, PatientProfile()) is Verdict.UNCERTAIN


# ── prior_therapy ─────────────────────────────────────────────────────────────
def test_prior_therapy_prohibited_received_fails():
    c = _crit(category="prior_therapy",
              predicate={"therapy_class": "checkpoint inhibitor", "relation": "prohibited"})
    assert _verdict(c, PatientProfile(prior_therapies=["checkpoint inhibitor"])) is Verdict.FAIL


def test_prior_therapy_prohibited_naive_passes():
    c = _crit(category="prior_therapy",
              predicate={"therapy_class": "checkpoint inhibitor", "relation": "prohibited"})
    assert _verdict(c, PatientProfile(treatment_naive=True)) is Verdict.PASS


def test_prior_therapy_unknown_is_uncertain():
    c = _crit(category="prior_therapy",
              predicate={"therapy_class": "checkpoint inhibitor", "relation": "prohibited"})
    assert _verdict(c, PatientProfile()) is Verdict.UNCERTAIN


def test_prior_therapy_prohibited_absent_from_incomplete_list_is_uncertain():
    # Regression: the class isn't in prior_therapies, the list is non-empty, and the patient
    # isn't treatment-naive. Absence from a free-text list is NOT proof it never happened
    # (esp. washout/event criteria) — must be UNCERTAIN, never a falsely confident PASS.
    c = _crit(category="prior_therapy",
              predicate={"therapy_class": "anti-tumor clinical trial", "relation": "prohibited"})
    assert _verdict(c, PatientProfile(prior_therapies=["major surgery"])) is Verdict.UNCERTAIN


def test_prior_therapy_required_absent_from_incomplete_list_is_uncertain():
    # Same logic for required-prior-therapy: not finding it in an incomplete list is unknown,
    # not a confident FAIL.
    c = _crit(category="prior_therapy",
              predicate={"therapy_class": "platinum chemotherapy", "relation": "required"})
    assert _verdict(c, PatientProfile(prior_therapies=["radiotherapy"])) is Verdict.UNCERTAIN


# ── no predicate / non-actionable ─────────────────────────────────────────────
def test_no_predicate_is_not_evaluated():
    c = _crit(category="comorbidity", predicate=None)
    assert _verdict(c, PatientProfile()) is Verdict.NOT_EVALUATED


def test_non_actionable_dropped_from_match():
    crits = [_crit(category="other", is_actionable=False, predicate=None)]
    result = match_criteria("NCT1", crits, PatientProfile())
    assert result.verdicts == []


# ── rollup signals ────────────────────────────────────────────────────────────
def _ecog(min_, max_): return {"scale": "ECOG", "min": min_, "max": max_}


def test_rollup_likely_eligible():
    crits = [
        _crit(category="performance_status", predicate=_ecog(0, 1)),
        _crit(category="disease_stage", predicate={"stage": ["IV"]}),
        _crit(category="comorbidity", predicate=None),  # not_evaluated, ignored for signal
    ]
    r = match_criteria("NCT1", crits, PatientProfile(ecog=1, stage="IV"))
    assert r.signal is TrialSignal.LIKELY_ELIGIBLE
    assert (r.n_pass, r.n_fail, r.n_not_evaluated) == (2, 0, 1)


def test_rollup_likely_excluded_on_any_fail():
    crits = [
        _crit(category="performance_status", predicate=_ecog(0, 1)),       # pass
        _crit(category="demographic", predicate={"min": 18}),              # fail (age 12)
    ]
    r = match_criteria("NCT1", crits, PatientProfile(ecog=1, age_years=12))
    assert r.signal is TrialSignal.LIKELY_EXCLUDED


def test_rollup_possible_on_uncertain():
    crits = [
        _crit(category="performance_status", predicate=_ecog(0, 1)),  # pass
        _crit(category="lab_value", predicate={"analyte": "ANC", "op": ">=", "value": 1500}),  # uncertain
    ]
    r = match_criteria("NCT1", crits, PatientProfile(ecog=1))
    assert r.signal is TrialSignal.POSSIBLE


def test_rollup_possible_when_nothing_evaluable():
    crits = [_crit(category="comorbidity", predicate=None)]
    r = match_criteria("NCT1", crits, PatientProfile())
    assert r.signal is TrialSignal.POSSIBLE


# ── patient-first ranking ─────────────────────────────────────────────────────
def test_rank_matches_orders_eligible_first_excluded_last():
    candidates = [
        {"nct_id": "NCT-EXCL", "brief_title": "B"},
        {"nct_id": "NCT-ELIG", "brief_title": "A"},
        {"nct_id": "NCT-NOCRIT", "brief_title": "C"},
    ]
    criteria_by_nct = {
        "NCT-ELIG": [_crit(category="performance_status", predicate=_ecog(0, 1))],   # pass
        "NCT-EXCL": [_crit(category="demographic", predicate={"min": 18})],          # fail (age 12)
        # NCT-NOCRIT: no criteria → possible, has_criteria False
    }
    profile = PatientProfile(ecog=1, age_years=12)
    ranked = rank_matches(candidates, criteria_by_nct, profile)

    assert [m.nct_id for m in ranked] == ["NCT-ELIG", "NCT-NOCRIT", "NCT-EXCL"]
    assert ranked[0].signal is TrialSignal.LIKELY_ELIGIBLE and ranked[0].has_criteria
    assert ranked[1].signal is TrialSignal.POSSIBLE and ranked[1].has_criteria is False
    assert ranked[2].signal is TrialSignal.LIKELY_EXCLUDED

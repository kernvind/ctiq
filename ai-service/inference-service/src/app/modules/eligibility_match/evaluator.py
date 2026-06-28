"""Pure, stateless predicate evaluation (ROADMAP step 6).

Compares a PatientProfile against a trial's structured eligibility predicates and returns a
per-criterion verdict + a trial-level signal. No I/O, no DB, no persistence — fully unit
testable and PHI-safe (nothing stored). The repository/service layers feed it dict rows.

Core idea: each predicate is a *test* on a patient attribute. Evaluate the test to
True/False/Unknown, then map by criterion_type:
  inclusion: True→PASS, False→FAIL, Unknown→UNCERTAIN
  exclusion: True→FAIL,  False→PASS, Unknown→UNCERTAIN (biomarker may override via
             unknown_status, e.g. "unknown EGFR status is excluded").
Criteria with no predicate (prose) are NOT_EVALUATED — surfaced for human review, not
counted against the signal. Non-actionable boilerplate is dropped before evaluation.
"""
from __future__ import annotations

from typing import Optional

from src.app.modules.eligibility_match.schemas import (
    CriterionVerdict,
    MatchResult,
    PatientProfile,
    TrialSignal,
    Verdict,
)

_INCLUSION = "inclusion"

# Marker status strings → present? (True/False); anything else / missing → None (unknown).
_PRESENT = {"mutated", "positive", "present", "detected", "sensitizing", "amplified", "expressed"}
_ABSENT = {"wild-type", "wildtype", "wt", "negative", "absent", "not detected", "none"}


def _to_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(op: Optional[str], lhs: float, rhs: float) -> Optional[bool]:
    if op == ">=":
        return lhs >= rhs
    if op == "<=":
        return lhs <= rhs
    if op == ">":
        return lhs > rhs
    if op == "<":
        return lhs < rhs
    if op in ("==", "="):
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    return None


def _marker_presence(value) -> Optional[bool]:
    """Interpret a patient's biomarker status string → present / absent / unknown."""
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in _PRESENT:
        return True
    if s in _ABSENT:
        return False
    if s in ("unknown", "untested", "indeterminate", ""):
        return None
    # A specific named alteration (e.g. "exon19del", "L858R") implies present.
    return True


def _map(test: Optional[bool], criterion_type: str, reason: str) -> tuple[Verdict, str]:
    """Map a tri-state test result to a verdict given inclusion/exclusion polarity."""
    if test is None:
        return Verdict.UNCERTAIN, reason
    if criterion_type == _INCLUSION:
        return (Verdict.PASS if test else Verdict.FAIL), reason
    return (Verdict.FAIL if test else Verdict.PASS), reason  # exclusion: trait present = fail


# ── per-category tests: return (test_result, reason) ─────────────────────────

def _eval_performance_status(pred: dict, p: PatientProfile) -> tuple[Optional[bool], str]:
    if p.ecog is None:
        return None, "patient ECOG unknown"
    lo, hi = pred.get("min"), pred.get("max")
    ok = (lo is None or p.ecog >= lo) and (hi is None or p.ecog <= hi)
    return ok, f"ECOG {p.ecog} vs required [{lo}, {hi}]"


def _eval_demographic(pred: dict, p: PatientProfile) -> tuple[Optional[bool], str]:
    if p.age_years is None:
        return None, "patient age unknown"
    lo, hi = pred.get("min"), pred.get("max")
    ok = (lo is None or p.age_years >= lo) and (hi is None or p.age_years <= hi)
    return ok, f"age {p.age_years} vs required [{lo}, {hi}]"


def _eval_disease_stage(pred: dict, p: PatientProfile) -> tuple[Optional[bool], str]:
    stages = [str(s).upper() for s in (pred.get("stage") or [])]
    if not stages:
        return None, "no stage in predicate"
    if p.stage is None:
        return None, "patient stage unknown"
    ok = p.stage.strip().upper() in stages
    return ok, f"stage {p.stage} vs {stages}"


def _eval_lab_value(pred: dict, p: PatientProfile) -> tuple[Optional[bool], str]:
    analyte, op, value = pred.get("analyte"), pred.get("op"), _to_float(pred.get("value"))
    if not analyte or value is None:
        return None, "incomplete lab predicate"
    patient_val = p.labs.get(analyte)
    if patient_val is None:
        return None, f"patient {analyte} unknown"
    return _compare(op, patient_val, value), f"{analyte} {patient_val} {op} {value}"


def _eval_biomarker(pred: dict, p: PatientProfile) -> tuple[Optional[bool], str]:
    marker = pred.get("marker")
    if not marker:
        return None, "no marker in predicate"
    raw = p.biomarkers.get(marker)
    op, value = pred.get("op"), _to_float(pred.get("value"))
    # Numeric threshold (e.g. PD-L1 >= 1).
    if op is not None and value is not None:
        pv = _to_float(raw)
        if pv is None:
            return None, f"patient {marker} value unknown"
        return _compare(op, pv, value), f"{marker} {pv} {op} {value}"
    # Presence/mutation test (e.g. EGFR sensitizing mutation).
    return _marker_presence(raw), f"{marker} status = {raw!r}"


_DISPATCH = {
    "performance_status": _eval_performance_status,
    "demographic": _eval_demographic,
    "disease_stage": _eval_disease_stage,
    "lab_value": _eval_lab_value,
    "biomarker": _eval_biomarker,
}


def _eval_prior_therapy(pred: dict, p: PatientProfile, criterion_type: str) -> tuple[Verdict, str]:
    """Prior therapy keys off `relation` (prohibited/required), not just polarity."""
    cls = pred.get("therapy_class")
    relation = pred.get("relation")
    received = None
    if cls and any(cls.lower() in t.lower() for t in p.prior_therapies):
        received = True
    elif p.treatment_naive is True:
        received = False
    elif p.prior_therapies:  # has a (different) therapy list but not this class
        received = False
    reason = f"prior {cls!r} received={received} (relation={relation})"
    if received is None:
        return Verdict.UNCERTAIN, reason
    if relation == "required":
        return (Verdict.PASS if received else Verdict.FAIL), reason
    # prohibited / excluded / default: receiving it disqualifies.
    return (Verdict.FAIL if received else Verdict.PASS), reason


def evaluate_criterion(criterion: dict, profile: PatientProfile) -> CriterionVerdict:
    """Evaluate one criterion dict (keys: criterion_type, category, text, predicate)."""
    ctype = criterion.get("criterion_type", _INCLUSION)
    category = criterion.get("category")
    text = criterion.get("text", "")
    pred = criterion.get("predicate")

    def _v(verdict: Verdict, reason: str) -> CriterionVerdict:
        return CriterionVerdict(
            criterion_type=ctype, category=category, text=text, verdict=verdict, reason=reason
        )

    if not pred:
        return _v(Verdict.NOT_EVALUATED, "no structured predicate (prose criterion)")

    if category == "prior_therapy":
        verdict, reason = _eval_prior_therapy(pred, profile, ctype)
        return _v(verdict, reason)

    fn = _DISPATCH.get(category)
    if fn is None:
        return _v(Verdict.NOT_EVALUATED, f"category {category!r} not deterministically evaluable")

    test, reason = fn(pred, profile)
    # Biomarker: unknown status can be forced to excluded per the trial.
    if test is None and category == "biomarker" and pred.get("unknown_status") == "excluded":
        return _v(Verdict.FAIL, reason + " → unknown treated as excluded")
    verdict, reason = _map(test, ctype, reason)
    return _v(verdict, reason)


def match_criteria(nct_id: str, criteria: list[dict], profile: PatientProfile) -> MatchResult:
    """Evaluate all actionable criteria and roll up to a trial-level signal."""
    verdicts = [
        evaluate_criterion(c, profile)
        for c in criteria
        if c.get("is_actionable", True)
    ]
    n_pass = sum(v.verdict == Verdict.PASS for v in verdicts)
    n_fail = sum(v.verdict == Verdict.FAIL for v in verdicts)
    n_uncertain = sum(v.verdict == Verdict.UNCERTAIN for v in verdicts)
    n_not_eval = sum(v.verdict == Verdict.NOT_EVALUATED for v in verdicts)

    if n_fail:
        signal = TrialSignal.LIKELY_EXCLUDED
    elif n_uncertain or n_pass == 0:  # missing data, or nothing evaluable → can't commit
        signal = TrialSignal.POSSIBLE
    else:
        signal = TrialSignal.LIKELY_ELIGIBLE

    return MatchResult(
        nct_id=nct_id, signal=signal,
        n_pass=n_pass, n_fail=n_fail, n_uncertain=n_uncertain, n_not_evaluated=n_not_eval,
        verdicts=verdicts,
    )

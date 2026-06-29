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
    MatchedTrial,
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


def _washout_days_since(cls: Optional[str], p: PatientProfile) -> Optional[int]:
    """Days since the patient last received `cls`, looked up in `washouts` by the same
    substring match used for prior_therapies (keeps the therapy vocab matching consistent)."""
    if not cls:
        return None
    needle = cls.lower()
    for event, days in p.washouts.items():
        if needle in event.lower():
            return days
    return None


def _eval_prior_therapy(pred: dict, p: PatientProfile, criterion_type: str) -> tuple[Verdict, str]:
    """Prior therapy keys off `relation` (prohibited/required), not just polarity.

    A *confident* received/not-received is asserted only from explicit evidence:
      - the therapy class appears in the patient's prior_therapies → received=True
      - the patient is treatment-naive                            → received=False
    Crucially, the class simply being ABSENT from a (free-text, possibly incomplete)
    prior_therapies list is NOT proof the patient never had it — so we stay UNCERTAIN
    rather than emitting a falsely confident PASS on a prohibited exclusion. This matters
    most for washout/event criteria the extractor mis-buckets here (recent surgery, other
    trials), which would never appear under "prior therapies" anyway. (A false PASS could
    clear an ineligible patient; UNCERTAIN surfaces it for review instead.)

    Washout (ROADMAP 6b): when the predicate carries `washout_days` (a "within N days" window)
    AND the patient supplied a days-since for the class, we evaluate the window directly —
    prohibited: enough time elapsed (days_since >= window) → PASS, still inside → FAIL;
    `required` is the inverse (must have occurred within the window). When the class was
    received but timing is unknown, we return UNCERTAIN (an honest unknown) instead of the old
    conservative FAIL, since we genuinely can't tell whether the patient is past the window.
    """
    cls = pred.get("therapy_class")
    relation = pred.get("relation")
    washout_days = pred.get("washout_days")

    received: Optional[bool] = None
    if cls and any(cls.lower() in t.lower() for t in p.prior_therapies):
        received = True
    elif p.treatment_naive is True:
        received = False

    # Windowed criterion with patient timing → evaluate the window directly.
    if washout_days is not None:
        days_since = _washout_days_since(cls, p)
        if days_since is not None:
            reason = f"prior {cls!r} {days_since}d ago vs {washout_days}d washout (relation={relation})"
            if relation == "required":
                return (Verdict.PASS if days_since <= washout_days else Verdict.FAIL), reason
            return (Verdict.PASS if days_since >= washout_days else Verdict.FAIL), reason
        if received is True:
            # Received, but we don't know when — can't place them inside/outside the window.
            return Verdict.UNCERTAIN, (
                f"prior {cls!r} received but timing unknown (within {washout_days}d window?)"
            )
        # Never received (treatment-naive) → the window is trivially satisfied.

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

    if not isinstance(category, str):
        return _v(Verdict.NOT_EVALUATED, f"category {category!r} not deterministically evaluable")
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


# Lower = better; the patient-first list leads with likely-eligible trials.
_SIGNAL_PRIORITY = {
    TrialSignal.LIKELY_ELIGIBLE: 0,
    TrialSignal.POSSIBLE: 1,
    TrialSignal.LIKELY_EXCLUDED: 2,
}


def rank_matches(
    candidates: list[dict],
    criteria_by_nct: dict[str, list[dict]],
    profile: PatientProfile,
) -> list[MatchedTrial]:
    """Patient-first: match each candidate (dict with nct_id + display fields) against the
    profile and rank — likely-eligible first, then fewest fails / most passes. Stable sort,
    so the candidate order (semantic relevance) is the final tiebreak.
    """
    matched: list[MatchedTrial] = []
    for c in candidates:
        nct_id = c["nct_id"]
        crits = criteria_by_nct.get(nct_id, [])
        res = match_criteria(nct_id, crits, profile)
        matched.append(
            MatchedTrial(
                nct_id=nct_id,
                brief_title=c.get("brief_title"),
                overall_status=c.get("overall_status"),
                phases=c.get("phases") or [],
                conditions=c.get("conditions") or [],
                lead_sponsor_name=c.get("lead_sponsor_name"),
                signal=res.signal,
                n_pass=res.n_pass, n_fail=res.n_fail,
                n_uncertain=res.n_uncertain, n_not_evaluated=res.n_not_evaluated,
                has_criteria=bool(crits),
                # Surface the failing criteria inline so the ranked list can explain an
                # exclusion without a per-trial drill-in.
                blockers=[v for v in res.verdicts if v.verdict == Verdict.FAIL],
            )
        )
    matched.sort(key=lambda m: (_SIGNAL_PRIORITY[m.signal], m.n_fail, -m.n_pass))
    return matched

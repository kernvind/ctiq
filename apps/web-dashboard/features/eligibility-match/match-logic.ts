import type { MatchedTrial, TrialSignal } from "@repo/generated-schemas-web";

export type Pair = { key: string; value: string };

export type ProfileForm = {
  age: string;
  sex: string;
  ecog: string;
  stage: string;
  treatmentNaive: boolean;
  biomarkers: Pair[];
  priorTherapies: string[];
  // event keyword (key) -> days since it last occurred (value, as text). Feeds washout matching.
  washouts: Pair[];
};

/**
 * Map the match form's raw string inputs into the PatientProfile sent to the matcher.
 * Pure so it can be unit-tested: blanks → null, numeric fields parsed, and empty
 * biomarker/therapy/washout rows dropped (trimmed). Washout rows also require a
 * non-negative integer day count (anything else is dropped, never sent as NaN).
 */
export function buildProfile(form: ProfileForm) {
  return {
    age_years: form.age ? Number(form.age) : null,
    sex: form.sex || null,
    ecog: form.ecog !== "" ? Number(form.ecog) : null,
    stage: form.stage.trim() || null,
    treatment_naive: form.treatmentNaive ? true : null,
    biomarkers: form.biomarkers
      .filter((b) => b.key.trim() && b.value.trim())
      .map((b) => ({ marker: b.key.trim(), value: b.value.trim() })),
    prior_therapies: form.priorTherapies.map((t) => t.trim()).filter(Boolean),
    labs: [],
    washouts: form.washouts
      // Drop blank event/value BEFORE Number() — Number("") is 0 (not NaN), which would
      // otherwise sneak an empty row through as days_since: 0.
      .map((w) => ({ event: w.key.trim(), value: w.value.trim() }))
      .filter((w) => w.event && w.value !== "")
      .map((w) => ({ event: w.event, days_since: Number(w.value) }))
      .filter((w) => Number.isInteger(w.days_since) && w.days_since >= 0),
  };
}

// Display order for the ranked list. UPPERCASE = the GraphQL enum's serialized names
// (the wire values), not the lowercase inference strings.
export const SIGNAL_ORDER: TrialSignal[] = [
  "LIKELY_ELIGIBLE",
  "POSSIBLE",
  "LIKELY_EXCLUDED",
];

/**
 * Did the deterministic matcher actually test this trial against the profile? True when at
 * least one criterion resolved to PASS/FAIL/UNCERTAIN. Trials with none — no structured
 * eligibility extracted yet, or only prose criteria the matcher can't evaluate — are NOT
 * meaningfully "Possible"; they're unknown. We surface them apart so the signal buckets stay
 * honest (a clinician shouldn't see "no data" disguised as a borderline match).
 */
export function isAssessable(t: MatchedTrial): boolean {
  return t.n_pass + t.n_fail + t.n_uncertain > 0;
}

/**
 * How many of a trial's actionable criteria the matcher could actually evaluate, vs the total.
 * `checked` = pass + fail + uncertain; `total` adds the prose criteria it couldn't assess.
 * Surfacing this ("8 of 12 checked") turns our honesty about coverage into a trust signal —
 * a clinician weighs a verdict differently when they know how much of it was machine-checked.
 */
export function criterionCoverage(t: MatchedTrial): { checked: number; total: number } {
  const checked = t.n_pass + t.n_fail + t.n_uncertain;
  return { checked, total: checked + t.n_not_evaluated };
}

/** Bucket the *assessable* trials by signal in display order, dropping empty buckets. */
export function groupBySignal(
  results: MatchedTrial[],
): { signal: TrialSignal; trials: MatchedTrial[] }[] {
  const assessable = results.filter(isAssessable);
  return SIGNAL_ORDER.map((signal) => ({
    signal,
    trials: assessable.filter((r) => r.signal === signal),
  })).filter((g) => g.trials.length > 0);
}

/**
 * Recruiting trials that matched the condition but the matcher couldn't assess (no structured
 * eligibility, or prose-only criteria). Shown in their own group below the ranked buckets —
 * still useful leads for manual review, just not auto-rankable. Preserves backend order.
 */
export function unassessedTrials(results: MatchedTrial[]): MatchedTrial[] {
  return results.filter((t) => !isAssessable(t));
}

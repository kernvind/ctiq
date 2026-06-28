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
};

/**
 * Map the match form's raw string inputs into the PatientProfile sent to the matcher.
 * Pure so it can be unit-tested: blanks → null, numeric fields parsed, and empty
 * biomarker/therapy rows dropped (trimmed).
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
  };
}

// Display order for the ranked list. UPPERCASE = the GraphQL enum's serialized names
// (the wire values), not the lowercase inference strings.
export const SIGNAL_ORDER: TrialSignal[] = [
  "LIKELY_ELIGIBLE",
  "POSSIBLE",
  "LIKELY_EXCLUDED",
];

/** Bucket ranked trials by signal in display order, dropping empty buckets. */
export function groupBySignal(
  results: MatchedTrial[],
): { signal: TrialSignal; trials: MatchedTrial[] }[] {
  return SIGNAL_ORDER.map((signal) => ({
    signal,
    trials: results.filter((r) => r.signal === signal),
  })).filter((g) => g.trials.length > 0);
}

import { describe, it, expect } from "vitest";
import type { MatchedTrial, TrialSignal } from "@repo/generated-schemas-web";
import {
  buildProfile,
  criterionCoverage,
  groupBySignal,
  isAssessable,
  unassessedTrials,
  type ProfileForm,
} from "./match-logic";

const EMPTY_FORM: ProfileForm = {
  age: "",
  sex: "",
  ecog: "",
  stage: "",
  treatmentNaive: false,
  biomarkers: [],
  priorTherapies: [],
  washouts: [],
};

describe("buildProfile", () => {
  it("maps blank fields to null and parses numbers", () => {
    const p = buildProfile({ ...EMPTY_FORM, age: "61", stage: "  IV  " });
    expect(p.age_years).toBe(61);
    expect(p.stage).toBe("IV");
    expect(p.sex).toBeNull();
    expect(p.treatment_naive).toBeNull();
  });

  it("treats ECOG 0 as a real value, not blank", () => {
    expect(buildProfile({ ...EMPTY_FORM, ecog: "0" }).ecog).toBe(0);
    expect(buildProfile({ ...EMPTY_FORM, ecog: "" }).ecog).toBeNull();
  });

  it("sets treatment_naive only when checked", () => {
    expect(buildProfile({ ...EMPTY_FORM, treatmentNaive: true }).treatment_naive).toBe(true);
  });

  it("drops empty/half-filled biomarker rows and trims the rest", () => {
    const p = buildProfile({
      ...EMPTY_FORM,
      biomarkers: [
        { key: " EGFR ", value: " wild-type " },
        { key: "PD-L1", value: "" }, // half-filled → dropped
        { key: "", value: "" }, // empty → dropped
      ],
    });
    expect(p.biomarkers).toEqual([{ marker: "EGFR", value: "wild-type" }]);
  });

  it("trims prior therapies and drops blanks", () => {
    const p = buildProfile({ ...EMPTY_FORM, priorTherapies: [" osimertinib ", "  ", ""] });
    expect(p.prior_therapies).toEqual(["osimertinib"]);
  });

  it("maps washout rows to {event, days_since}, trimming the event", () => {
    const p = buildProfile({
      ...EMPTY_FORM,
      washouts: [{ key: " chemotherapy ", value: "14" }],
    });
    expect(p.washouts).toEqual([{ event: "chemotherapy", days_since: 14 }]);
  });

  it("drops washout rows with a blank event or a non-integer/negative day count", () => {
    const p = buildProfile({
      ...EMPTY_FORM,
      washouts: [
        { key: "surgery", value: "60" }, // valid
        { key: "", value: "30" }, // blank event → dropped
        { key: "radiation", value: "" }, // blank days → NaN → dropped
        { key: "chemo", value: "1.5" }, // non-integer → dropped
        { key: "trial", value: "-5" }, // negative → dropped
      ],
    });
    expect(p.washouts).toEqual([{ event: "surgery", days_since: 60 }]);
  });
});

// Default counts make a trial *assessable* (n_pass:1); pass `counts` to override — e.g. all
// zero for an unassessable trial (no extracted eligibility or prose-only).
const trial = (
  nct_id: string,
  signal: TrialSignal,
  counts: Partial<
    Pick<
      MatchedTrial,
      "n_pass" | "n_fail" | "n_uncertain" | "n_not_evaluated" | "has_criteria"
    >
  > = {},
): MatchedTrial =>
  ({
    nct_id,
    signal,
    has_criteria: true,
    n_pass: 1,
    n_fail: 0,
    n_uncertain: 0,
    n_not_evaluated: 0,
    brief_title: null,
    overall_status: null,
    phases: [],
    conditions: [],
    lead_sponsor_name: null,
    blockers: [],
    ...counts,
  }) as MatchedTrial;

describe("isAssessable", () => {
  it("is true when any criterion resolved to pass/fail/uncertain", () => {
    expect(isAssessable(trial("A", "POSSIBLE", { n_pass: 0, n_uncertain: 1 }))).toBe(true);
    expect(isAssessable(trial("B", "LIKELY_EXCLUDED", { n_pass: 0, n_fail: 1 }))).toBe(true);
  });

  it("is false when nothing was evaluated (no criteria, or prose-only)", () => {
    expect(isAssessable(trial("A", "POSSIBLE", { n_pass: 0, has_criteria: false }))).toBe(false);
    expect(
      isAssessable(trial("B", "POSSIBLE", { n_pass: 0, n_not_evaluated: 3 })),
    ).toBe(false);
  });
});

describe("criterionCoverage", () => {
  it("counts checked (pass+fail+uncertain) vs total (incl. not-evaluated)", () => {
    const cov = criterionCoverage(
      trial("A", "POSSIBLE", { n_pass: 5, n_fail: 2, n_uncertain: 1, n_not_evaluated: 4 }),
    );
    expect(cov).toEqual({ checked: 8, total: 12 });
  });

  it("reports full coverage when nothing is left unevaluated", () => {
    const cov = criterionCoverage(
      trial("A", "LIKELY_ELIGIBLE", { n_pass: 3, n_not_evaluated: 0 }),
    );
    expect(cov).toEqual({ checked: 3, total: 3 });
  });
});

describe("unassessedTrials", () => {
  it("returns only the unassessable trials, preserving order", () => {
    const out = unassessedTrials([
      trial("A", "LIKELY_ELIGIBLE"),
      trial("B", "POSSIBLE", { n_pass: 0, has_criteria: false }),
      trial("C", "POSSIBLE", { n_pass: 0, n_not_evaluated: 2 }),
    ]);
    expect(out.map((t) => t.nct_id)).toEqual(["B", "C"]);
  });
});

describe("groupBySignal", () => {
  it("excludes unassessable trials from the signal buckets", () => {
    const groups = groupBySignal([
      trial("A", "LIKELY_ELIGIBLE"),
      trial("B", "POSSIBLE", { n_pass: 0, has_criteria: false }),
    ]);
    expect(groups).toHaveLength(1);
    expect(groups[0].signal).toBe("LIKELY_ELIGIBLE");
    expect(groups[0].trials.map((t) => t.nct_id)).toEqual(["A"]);
  });

  it("orders eligible → possible → excluded and drops empty buckets", () => {
    const groups = groupBySignal([
      trial("A", "LIKELY_EXCLUDED"),
      trial("B", "LIKELY_ELIGIBLE"),
      trial("C", "POSSIBLE"),
    ]);
    expect(groups.map((g) => g.signal)).toEqual([
      "LIKELY_ELIGIBLE",
      "POSSIBLE",
      "LIKELY_EXCLUDED",
    ]);
  });

  it("collects multiple trials under one signal, preserving order", () => {
    const groups = groupBySignal([trial("A", "POSSIBLE"), trial("B", "POSSIBLE")]);
    expect(groups).toHaveLength(1);
    expect(groups[0].trials.map((t) => t.nct_id)).toEqual(["A", "B"]);
  });

  it("regression: matches the UPPERCASE wire enum (lowercase produced zero groups)", () => {
    expect(groupBySignal([trial("A", "LIKELY_ELIGIBLE")])).toHaveLength(1);
  });

  it("returns nothing for an empty result set", () => {
    expect(groupBySignal([])).toEqual([]);
  });
});

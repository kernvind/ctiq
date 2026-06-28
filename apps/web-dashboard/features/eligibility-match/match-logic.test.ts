import { describe, it, expect } from "vitest";
import type { MatchedTrial, TrialSignal } from "@repo/generated-schemas-web";
import { buildProfile, groupBySignal, type ProfileForm } from "./match-logic";

const EMPTY_FORM: ProfileForm = {
  age: "",
  sex: "",
  ecog: "",
  stage: "",
  treatmentNaive: false,
  biomarkers: [],
  priorTherapies: [],
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
});

describe("groupBySignal", () => {
  const trial = (nct_id: string, signal: TrialSignal): MatchedTrial =>
    ({
      nct_id,
      signal,
      has_criteria: true,
      n_pass: 0,
      n_fail: 0,
      n_uncertain: 0,
      n_not_evaluated: 0,
      brief_title: null,
      overall_status: null,
      phases: [],
      conditions: [],
      lead_sponsor_name: null,
    }) as MatchedTrial;

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

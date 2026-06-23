import { describe, it, expect } from "vitest";
import { rigorBadges } from "./trial-rigor";

describe("rigorBadges", () => {
  it("renders allocation, masking and model in reading order", () => {
    expect(
      rigorBadges({
        allocation: "RANDOMIZED",
        masking: "DOUBLE",
        intervention_model: "PARALLEL",
      }),
    ).toEqual(["Randomized", "Double-blind", "Parallel"]);
  });

  it("maps masking NONE to the clinician-facing 'Open-label'", () => {
    expect(rigorBadges({ masking: "NONE" })).toEqual(["Open-label"]);
  });

  it("is case/separator-insensitive on the input enums", () => {
    expect(
      rigorBadges({ allocation: "non-randomized", masking: "single" }),
    ).toEqual(["Non-randomized", "Single-blind"]);
  });

  it("drops non-informative allocation 'NA' and any missing fields", () => {
    expect(
      rigorBadges({
        allocation: "NA",
        masking: null,
        intervention_model: "CROSSOVER",
      }),
    ).toEqual(["Crossover"]);
  });

  it("returns an empty array when no design info is present", () => {
    expect(rigorBadges({})).toEqual([]);
    expect(
      rigorBadges({ allocation: null, masking: undefined, intervention_model: "" }),
    ).toEqual([]);
  });

  it("falls back to a title-cased label for an unrecognized enum value", () => {
    expect(rigorBadges({ intervention_model: "SOME_NEW_MODEL" })).toEqual([
      "Some new model",
    ]);
  });
});

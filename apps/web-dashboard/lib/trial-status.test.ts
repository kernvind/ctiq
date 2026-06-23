import { describe, it, expect } from "vitest";
import { isOpenForEnrollment, partitionByEnrollment } from "./trial-status";

describe("isOpenForEnrollment", () => {
  it.each([
    "RECRUITING",
    "NOT_YET_RECRUITING",
    "ENROLLING_BY_INVITATION",
    "AVAILABLE",
  ])("treats %s as open for enrollment", (status) => {
    expect(isOpenForEnrollment(status)).toBe(true);
  });

  it.each([
    "COMPLETED",
    "ACTIVE_NOT_RECRUITING",
    "TERMINATED",
    "WITHDRAWN",
    "SUSPENDED",
    "NO_LONGER_AVAILABLE",
    "UNKNOWN",
  ])("treats %s as not open for enrollment", (status) => {
    expect(isOpenForEnrollment(status)).toBe(false);
  });

  it("normalizes case and separators (spaces/commas) before classifying", () => {
    expect(isOpenForEnrollment("Recruiting")).toBe(true);
    expect(isOpenForEnrollment("Active, not recruiting")).toBe(false);
  });

  it("treats null/undefined/empty as not open (fail safe — never imply actionable)", () => {
    expect(isOpenForEnrollment(null)).toBe(false);
    expect(isOpenForEnrollment(undefined)).toBe(false);
    expect(isOpenForEnrollment("")).toBe(false);
  });
});

describe("partitionByEnrollment", () => {
  const trial = (nct: string, overall_status: string) => ({
    nct_id: nct,
    overall_status,
  });

  it("splits into open vs closed, preserving input order within each group", () => {
    const trials = [
      trial("NCT1", "RECRUITING"),
      trial("NCT2", "COMPLETED"),
      trial("NCT3", "NOT_YET_RECRUITING"),
      trial("NCT4", "TERMINATED"),
    ];

    const { open, closed } = partitionByEnrollment(trials);

    expect(open.map((t) => t.nct_id)).toEqual(["NCT1", "NCT3"]);
    expect(closed.map((t) => t.nct_id)).toEqual(["NCT2", "NCT4"]);
  });

  it("returns empty groups for an empty input", () => {
    expect(partitionByEnrollment([])).toEqual({ open: [], closed: [] });
  });
});

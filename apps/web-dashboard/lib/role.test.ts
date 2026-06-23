import { describe, it, expect } from "vitest";
import { roleLabel } from "./role";

describe("roleLabel", () => {
  it.each([
    ["PATIENT", "Patient"],
    ["CLINICIAN", "Clinician"],
    ["ANALYST", "Analyst"],
    ["ADMIN", "Admin"],
  ])("maps %s to its display label %s", (role, label) => {
    expect(roleLabel(role)).toBe(label);
  });

  it("is case-insensitive", () => {
    expect(roleLabel("clinician")).toBe("Clinician");
  });

  it("falls back to the raw value for an unknown role", () => {
    expect(roleLabel("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });

  it("returns an empty string for null/undefined", () => {
    expect(roleLabel(null)).toBe("");
    expect(roleLabel(undefined)).toBe("");
  });
});

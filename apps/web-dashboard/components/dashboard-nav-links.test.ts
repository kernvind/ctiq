import { describe, it, expect } from "vitest";
import { NAV_LINKS, visibleNavLinks, type Role } from "./dashboard-nav-links";

const ALL_ROLES: Role[] = ["PATIENT", "CLINICIAN", "ANALYST", "ADMIN"];

const labelsFor = (role: Role) => visibleNavLinks(role).map((l) => l.label);

describe("visibleNavLinks", () => {
  it("shows Eligibility Match only to clinicians (mirrors the api-core RBAC gate)", () => {
    expect(labelsFor("CLINICIAN")).toContain("Eligibility Match");
    for (const role of ["PATIENT", "ANALYST", "ADMIN"] as Role[]) {
      expect(labelsFor(role)).not.toContain("Eligibility Match");
    }
  });

  it("shows Portfolio Screening only to clinicians (site-payer wedge, same RBAC gate)", () => {
    expect(labelsFor("CLINICIAN")).toContain("Portfolio Screening");
    for (const role of ["PATIENT", "ANALYST", "ADMIN"] as Role[]) {
      expect(labelsFor(role)).not.toContain("Portfolio Screening");
    }
  });

  it("shows Landscapes only to analysts", () => {
    expect(labelsFor("ANALYST")).toContain("Landscapes");
    for (const role of ["PATIENT", "CLINICIAN", "ADMIN"] as Role[]) {
      expect(labelsFor(role)).not.toContain("Landscapes");
    }
  });

  it("shows the common links to every role", () => {
    for (const role of ALL_ROLES) {
      expect(labelsFor(role)).toEqual(
        expect.arrayContaining(["Overview", "Trial Search", "Saved"]),
      );
    }
  });

  it("every link has an icon (the mobile bottom bar renders one per tab)", () => {
    for (const link of NAV_LINKS) {
      expect(link.icon).toBeTruthy();
    }
  });

  it("Eligibility Match has a compact mobile label", () => {
    const match = NAV_LINKS.find((l) => l.href === "/dashboard/match");
    expect(match?.shortLabel).toBe("Match");
  });
});

import { describe, it, expect } from "vitest";
import { formatAgeYears, formatAgeBound, formatAgeRange } from "./format-age";

describe("formatAgeYears", () => {
  it("formats whole years plainly", () => {
    expect(formatAgeYears(18)).toBe("18y");
    expect(formatAgeYears(65)).toBe("65y");
  });

  it("converts sub-year ages to months (the 0.0833y bug)", () => {
    expect(formatAgeYears(1 / 12)).toBe("1mo"); // "1 Month"
    expect(formatAgeYears(2 / 12)).toBe("2mo");
    expect(formatAgeYears(0.5)).toBe("6mo");
  });

  it("converts very small ages to days", () => {
    expect(formatAgeYears(5 / 365)).toBe("5d"); // "5 Days"
  });

  it("renders age 0 as years (newborn), not 0 days", () => {
    expect(formatAgeYears(0)).toBe("0y");
  });

  it("rounds away floating-point noise rather than printing a long decimal", () => {
    expect(formatAgeYears(17.999999)).toBe("18y");
    expect(formatAgeYears(0.08333333333333333)).toBe("1mo");
  });

  it("keeps a meaningful fractional year when present", () => {
    expect(formatAgeYears(17.5)).toBe("17.5y");
  });

  it("returns null for null/undefined", () => {
    expect(formatAgeYears(null)).toBeNull();
    expect(formatAgeYears(undefined)).toBeNull();
  });
});

describe("formatAgeBound", () => {
  it("prefers the exact CT.gov raw string over the parsed float", () => {
    expect(formatAgeBound("1 Month", 0.08333333333333333)).toBe("1 Month");
    expect(formatAgeBound("18 Years", 18)).toBe("18 Years");
  });

  it("falls back to the formatted float when raw is absent/blank", () => {
    expect(formatAgeBound(null, 1 / 12)).toBe("1mo");
    expect(formatAgeBound("   ", 18)).toBe("18y");
  });

  it("returns null when neither raw nor years is present", () => {
    expect(formatAgeBound(null, null)).toBeNull();
  });
});

describe("formatAgeRange", () => {
  it("uses raw strings for each bound when present", () => {
    expect(
      formatAgeRange(
        { raw: "1 Month", years: 1 / 12 },
        { raw: "18 Years", years: 18 },
      ),
    ).toBe("1 Month – 18 Years");
  });

  it("falls back to formatted floats per bound", () => {
    expect(
      formatAgeRange({ years: 1 / 12 }, { years: 18 }),
    ).toBe("1mo – 18y");
  });

  it("shows whichever bound is present", () => {
    expect(formatAgeRange({ raw: "18 Years" }, {})).toBe("18 Years");
    expect(formatAgeRange({}, { years: 65 })).toBe("65y");
  });

  it("returns an empty string when neither bound is present", () => {
    expect(formatAgeRange({}, {})).toBe("");
  });
});

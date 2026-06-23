import { describe, it, expect } from "vitest";
import { parseCompareIds, buildCompareHref, MAX_COMPARE } from "./compare-ids";

describe("parseCompareIds", () => {
  it("parses a comma-separated list into upper-cased NCT ids", () => {
    expect(parseCompareIds("nct00000001, NCT00000002")).toEqual([
      "NCT00000001",
      "NCT00000002",
    ]);
  });

  it("drops malformed ids and keeps the valid ones", () => {
    expect(
      parseCompareIds("NCT00000001,garbage,NCT00000002"),
    ).toEqual(["NCT00000001", "NCT00000002"]);
  });

  it("de-duplicates repeated ids (case-insensitively)", () => {
    expect(parseCompareIds("NCT00000001,nct00000001")).toEqual([
      "NCT00000001",
    ]);
  });

  it(`caps the list at MAX_COMPARE (${MAX_COMPARE})`, () => {
    const many = Array.from(
      { length: MAX_COMPARE + 2 },
      (_, i) => `NCT0000000${i}`,
    ).join(",");
    expect(parseCompareIds(many)).toHaveLength(MAX_COMPARE);
  });

  it("accepts the array form of a query param", () => {
    expect(parseCompareIds(["NCT00000001", "NCT00000002"])).toEqual([
      "NCT00000001",
      "NCT00000002",
    ]);
  });

  it("returns an empty list for undefined/empty input", () => {
    expect(parseCompareIds(undefined)).toEqual([]);
    expect(parseCompareIds("")).toEqual([]);
    expect(parseCompareIds(",, ,")).toEqual([]);
  });
});

describe("buildCompareHref", () => {
  it("builds the /compare URL from selected ids", () => {
    expect(buildCompareHref(["NCT00000001", "NCT00000002"])).toBe(
      "/compare?ids=NCT00000001,NCT00000002",
    );
  });

  it("normalizes, de-dupes and caps via the same rules as parseCompareIds", () => {
    expect(buildCompareHref(["nct00000001", "NCT00000001"])).toBe(
      "/compare?ids=NCT00000001",
    );
  });

  it("round-trips with parseCompareIds", () => {
    const ids = ["NCT00000001", "NCT00000002"];
    const href = buildCompareHref(ids);
    const query = href.split("ids=")[1];
    expect(parseCompareIds(query)).toEqual(ids);
  });
});

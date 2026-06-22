import { describe, it, expect, vi, beforeEach } from "vitest";

const { searchTrialsQueryMock } = vi.hoisted(() => ({
  searchTrialsQueryMock: vi.fn(),
}));

vi.mock("@repo/generated-schemas-web", () => ({
  sdk: { searchTrials_query: searchTrialsQueryMock },
}));

import { searchTrialsAction } from "./actions";

// A query that satisfies ZodTrialSearchSchema (q: min 10, max 500 chars).
const VALID_QUERY = "advanced melanoma phase 3 trials";

describe("searchTrialsAction", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns a validation error (echoing the raw query) and never calls the API for too-short input", async () => {
    const res = await searchTrialsAction("short");

    expect(res?.error).toBeTruthy();
    expect(res?.query).toBe("short");
    expect(res?.results).toBeUndefined();
    expect(searchTrialsQueryMock).not.toHaveBeenCalled();
  });

  it("returns the results and the validated query on success", async () => {
    const cards = [{ nctId: "NCT00000001" }];
    searchTrialsQueryMock.mockResolvedValue({ searchTrials: cards });

    const res = await searchTrialsAction(VALID_QUERY);

    expect(searchTrialsQueryMock).toHaveBeenCalledWith({
      q: { q: VALID_QUERY },
    });
    expect(res).toEqual({ results: cards, query: VALID_QUERY });
  });

  it("surfaces the GraphQL error message (with the query) on failure", async () => {
    searchTrialsQueryMock.mockRejectedValue({
      response: { errors: [{ message: "upstream unavailable" }] },
    });

    const res = await searchTrialsAction(VALID_QUERY);

    expect(res).toEqual({
      error: "upstream unavailable",
      query: VALID_QUERY,
    });
  });

  it("falls back to a generic message when the error carries no GraphQL message", async () => {
    searchTrialsQueryMock.mockRejectedValue(new Error("network down"));

    const res = await searchTrialsAction(VALID_QUERY);

    expect(res).toEqual({
      error: "Search failed. Please try again.",
      query: VALID_QUERY,
    });
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";

const { trialQueryMock } = vi.hoisted(() => ({
  trialQueryMock: vi.fn(),
}));

vi.mock("@repo/generated-schemas-web", () => ({
  sdk: { trial_query: trialQueryMock },
}));

import { getTrial } from "./actions";

describe("getTrial", () => {
  beforeEach(() => vi.clearAllMocks());

  it("queries with the upper-cased NCT id and returns the trial", async () => {
    const trial = { nctId: "NCT01234567" };
    trialQueryMock.mockResolvedValue({ trial });

    const res = await getTrial("nct01234567");

    expect(trialQueryMock).toHaveBeenCalledWith({ nctId: "NCT01234567" });
    expect(res).toBe(trial);
  });

  it("returns null when no trial matches the id", async () => {
    trialQueryMock.mockResolvedValue({ trial: null });

    expect(await getTrial("NCT99999999")).toBeNull();
  });

  it("returns null when the query omits the trial field entirely", async () => {
    trialQueryMock.mockResolvedValue({});

    expect(await getTrial("NCT99999999")).toBeNull();
  });

  it("rethrows transport/backend errors for the caller to handle", async () => {
    const err = new Error("boom");
    trialQueryMock.mockRejectedValue(err);

    await expect(getTrial("NCT01234567")).rejects.toBe(err);
  });
});

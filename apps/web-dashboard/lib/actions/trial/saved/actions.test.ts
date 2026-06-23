import { describe, it, expect, vi, beforeEach } from "vitest";

const { withAuthedSdkMock, saveMock, unsaveMock } = vi.hoisted(() => ({
  withAuthedSdkMock: vi.fn(),
  saveMock: vi.fn(),
  unsaveMock: vi.fn(),
}));

vi.mock("@/lib/authed-sdk", () => ({ withAuthedSdk: withAuthedSdkMock }));

import { saveTrialAction, unsaveTrialAction } from "./actions";

// withAuthedSdk(fn) just runs fn against a fake sdk here.
const fakeSdk = {
  saveTrial_mutation: saveMock,
  unsaveTrial_mutation: unsaveMock,
};

describe("saved-trial actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    withAuthedSdkMock.mockImplementation((fn) => fn(fakeSdk));
  });

  it("saveTrialAction calls saveTrial_mutation with the nctId and reports ok", async () => {
    saveMock.mockResolvedValue({ saveTrial: { id: "s1", nctId: "NCT01" } });

    const res = await saveTrialAction("NCT01");

    expect(saveMock).toHaveBeenCalledWith({ nctId: "NCT01" });
    expect(res).toEqual({ ok: true });
  });

  it("unsaveTrialAction calls unsaveTrial_mutation and reports ok", async () => {
    unsaveMock.mockResolvedValue({ unsaveTrial: true });

    const res = await unsaveTrialAction("NCT01");

    expect(unsaveMock).toHaveBeenCalledWith({ nctId: "NCT01" });
    expect(res).toEqual({ ok: true });
  });

  it("surfaces the GraphQL error message on failure", async () => {
    saveMock.mockRejectedValue({
      response: { errors: [{ message: "Unauthorized" }] },
    });

    const res = await saveTrialAction("NCT01");

    expect(res).toEqual({ ok: false, error: "Unauthorized" });
  });

  it("falls back to a generic message when there's no GraphQL message", async () => {
    unsaveMock.mockRejectedValue(new Error("network"));

    const res = await unsaveTrialAction("NCT01");

    expect(res).toEqual({
      ok: false,
      error: "Something went wrong. Please try again.",
    });
  });
});

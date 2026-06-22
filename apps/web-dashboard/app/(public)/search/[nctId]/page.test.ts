import { describe, it, expect, vi, beforeEach } from "vitest";

const { notFoundMock, getTrialMock, trialDetailViewMock } = vi.hoisted(() => ({
  // notFound() halts rendering by throwing in Next; model that with a sentinel.
  notFoundMock: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  getTrialMock: vi.fn(),
  trialDetailViewMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({ notFound: notFoundMock }));
vi.mock("@/lib/actions/trial/details/actions", () => ({
  getTrial: getTrialMock,
}));
vi.mock("@/components/trial-detail-view", () => ({
  TrialDetailView: trialDetailViewMock,
}));

// ZodNctIdSchema is intentionally NOT mocked — these tests exercise the real guard.
import Page from "./page";

const render = (nctId: string) => Page({ params: Promise.resolve({ nctId }) });

describe("public trial detail page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("notFound()s on a malformed NCT id and never hits the backend", async () => {
    await expect(render("not-an-nct-id")).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
    expect(getTrialMock).not.toHaveBeenCalled();
  });

  it("renders TrialDetailView with the trial for a valid id that resolves", async () => {
    const trial = { nctId: "NCT01234567" };
    getTrialMock.mockResolvedValue(trial);

    const result = await render("NCT01234567");

    expect(getTrialMock).toHaveBeenCalledWith("NCT01234567");
    expect(result.type).toBe(trialDetailViewMock);
    expect(result.props.trial).toBe(trial);
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  it("notFound()s when the id is valid but no trial matches", async () => {
    getTrialMock.mockResolvedValue(null);

    await expect(render("NCT99999999")).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFoundMock).toHaveBeenCalledTimes(1);
  });

  it("shows an inline error (not notFound) when the backend call throws", async () => {
    getTrialMock.mockRejectedValue(new Error("upstream down"));

    const result = await render("NCT01234567");

    expect(result.type).toBe("p");
    expect(result.props.children).toContain("Could not load this trial");
    expect(notFoundMock).not.toHaveBeenCalled();
  });
});

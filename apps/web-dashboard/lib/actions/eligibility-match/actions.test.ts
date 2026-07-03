import { describe, it, expect, vi, beforeEach } from "vitest";

const { withAuthedSdkMock, matchTrialsMock, matchTrialMock, screenPortfolioMock } =
  vi.hoisted(() => ({
    withAuthedSdkMock: vi.fn(),
    matchTrialsMock: vi.fn(),
    matchTrialMock: vi.fn(),
    screenPortfolioMock: vi.fn(),
  }));

vi.mock("@/lib/authed-sdk", () => ({ withAuthedSdk: withAuthedSdkMock }));

import {
  matchTrialsAction,
  matchTrialAction,
  screenPortfolioAction,
} from "./actions";

const fakeSdk = {
  matchTrials_mutation: matchTrialsMock,
  matchTrial_mutation: matchTrialMock,
  screenPortfolio_mutation: screenPortfolioMock,
};

const validProfile = { ecog: 1, stage: "IV", biomarkers: [], prior_therapies: [], labs: [] };

describe("eligibility-match actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    withAuthedSdkMock.mockImplementation((fn) => fn(fakeSdk));
  });

  describe("matchTrialsAction", () => {
    it("validates, calls matchTrials_mutation, and returns the ranked results", async () => {
      matchTrialsMock.mockResolvedValue({ matchTrials: [{ nct_id: "NCT1" }] });

      const res = await matchTrialsAction({
        condition: "melanoma",
        profile: validProfile,
      });

      expect(matchTrialsMock).toHaveBeenCalledWith(
        expect.objectContaining({ condition: "melanoma" }),
      );
      expect(res).toEqual({ results: [{ nct_id: "NCT1" }] });
    });

    it("returns a zod error (and never calls the sdk) for an invalid condition", async () => {
      const res = await matchTrialsAction({ condition: "x", profile: validProfile });

      expect(matchTrialsMock).not.toHaveBeenCalled();
      expect(res?.error).toBeTruthy();
    });

    it("surfaces the GraphQL error message on failure", async () => {
      matchTrialsMock.mockRejectedValue({
        response: { errors: [{ message: "Insufficient permissions" }] },
      });

      const res = await matchTrialsAction({ condition: "melanoma", profile: validProfile });

      expect(res).toEqual({ error: "Insufficient permissions" });
    });
  });

  describe("matchTrialAction", () => {
    it("validates, calls matchTrial_mutation, and returns the result", async () => {
      matchTrialMock.mockResolvedValue({ matchTrial: { nct_id: "NCT01234567" } });

      const res = await matchTrialAction({ nctId: "NCT01234567", profile: validProfile });

      expect(matchTrialMock).toHaveBeenCalledWith(
        expect.objectContaining({ nctId: "NCT01234567" }),
      );
      expect(res).toEqual({ result: { nct_id: "NCT01234567" } });
    });

    it("maps a null match (no extracted criteria) to result: null", async () => {
      matchTrialMock.mockResolvedValue({ matchTrial: null });

      const res = await matchTrialAction({ nctId: "NCT01234567", profile: validProfile });

      expect(res).toEqual({ result: null });
    });

    it("returns a zod error for a malformed nct id", async () => {
      const res = await matchTrialAction({ nctId: "bad", profile: validProfile });

      expect(matchTrialMock).not.toHaveBeenCalled();
      expect(res?.error).toBeTruthy();
    });
  });

  describe("screenPortfolioAction", () => {
    it("validates the profile, calls screenPortfolio_mutation, and returns the results", async () => {
      screenPortfolioMock.mockResolvedValue({ screenPortfolio: [{ nct_id: "NCT1" }] });

      const res = await screenPortfolioAction(validProfile);

      expect(screenPortfolioMock).toHaveBeenCalledWith(
        expect.objectContaining({ profile: expect.objectContaining({ ecog: 1 }) }),
      );
      expect(res).toEqual({ results: [{ nct_id: "NCT1" }] });
    });

    it("returns a zod error (and never calls the sdk) for an invalid profile", async () => {
      const res = await screenPortfolioAction({ ecog: 99 }); // ecog out of [0,4]

      expect(screenPortfolioMock).not.toHaveBeenCalled();
      expect(res?.error).toBeTruthy();
    });

    it("surfaces the GraphQL error message on failure", async () => {
      screenPortfolioMock.mockRejectedValue({
        response: { errors: [{ message: "Insufficient permissions" }] },
      });

      const res = await screenPortfolioAction(validProfile);

      expect(res).toEqual({ error: "Insufficient permissions" });
    });
  });
});

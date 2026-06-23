import { describe, it, expect, vi, beforeEach } from "vitest";

const { withAuthedSdkMock, createMock, deleteMock, markSeenMock } = vi.hoisted(
  () => ({
    withAuthedSdkMock: vi.fn(),
    createMock: vi.fn(),
    deleteMock: vi.fn(),
    markSeenMock: vi.fn(),
  }),
);

vi.mock("@/lib/authed-sdk", () => ({ withAuthedSdk: withAuthedSdkMock }));

import {
  createLandscapeAction,
  deleteLandscapeAction,
  markLandscapeSeenAction,
} from "./actions";

const fakeSdk = {
  createLandscape_mutation: createMock,
  deleteLandscape_mutation: deleteMock,
  markLandscapeSeen_mutation: markSeenMock,
};

const VALID = { name: "GLP-1 obesity", q: "phase 3 GLP-1 obesity trials" };

describe("landscape actions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    withAuthedSdkMock.mockImplementation((fn) => fn(fakeSdk));
  });

  describe("createLandscapeAction", () => {
    it("validates then creates with the parsed input", async () => {
      createMock.mockResolvedValue({ createLandscape: { id: "l1" } });

      const res = await createLandscapeAction(VALID);

      expect(createMock).toHaveBeenCalledWith({
        input: { name: "GLP-1 obesity", q: "phase 3 GLP-1 obesity trials" },
      });
      expect(res).toEqual({ ok: true });
    });

    it("rejects an invalid input (short query) without calling the API", async () => {
      const res = await createLandscapeAction({ name: "x", q: "short" });

      expect(res.ok).toBe(false);
      expect(createMock).not.toHaveBeenCalled();
    });

    it("surfaces the server error message on failure", async () => {
      createMock.mockRejectedValue({
        response: { errors: [{ message: "Unauthorized" }] },
      });

      const res = await createLandscapeAction(VALID);

      expect(res).toEqual({ ok: false, error: "Unauthorized" });
    });
  });

  it("deleteLandscapeAction deletes by id", async () => {
    deleteMock.mockResolvedValue({ deleteLandscape: true });

    const res = await deleteLandscapeAction("l1");

    expect(deleteMock).toHaveBeenCalledWith({ id: "l1" });
    expect(res).toEqual({ ok: true });
  });

  it("markLandscapeSeenAction sends the id + seen nct ids", async () => {
    markSeenMock.mockResolvedValue({ markLandscapeSeen: { id: "l1" } });

    const res = await markLandscapeSeenAction("l1", ["NCT1", "NCT2"]);

    expect(markSeenMock).toHaveBeenCalledWith({
      id: "l1",
      nctIds: ["NCT1", "NCT2"],
    });
    expect(res).toEqual({ ok: true });
  });
});

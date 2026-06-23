import { describe, it, expect, vi, beforeEach } from "vitest";

const { cookieStore, getAuthedSdkMock, meQueryMock } = vi.hoisted(() => ({
  cookieStore: { get: vi.fn() },
  getAuthedSdkMock: vi.fn(),
  meQueryMock: vi.fn(),
}));

vi.mock("next/headers", () => ({ cookies: vi.fn(async () => cookieStore) }));
vi.mock("@repo/generated-schemas-web", () => ({
  getAuthedSdk: getAuthedSdkMock,
}));

import { getCurrentUser } from "./actions";

describe("getCurrentUser", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAuthedSdkMock.mockReturnValue({ me_query: meQueryMock });
  });

  it("returns the user when a token is present and the query resolves", async () => {
    cookieStore.get.mockReturnValue({ value: "access-tok" });
    const me = { id: "u1", email: "a@example.com", name: "Al", role: "CLINICIAN" };
    meQueryMock.mockResolvedValue({ me });

    const result = await getCurrentUser();

    expect(getAuthedSdkMock).toHaveBeenCalledWith("access-tok");
    expect(result).toEqual(me);
  });

  it("returns null (without calling the API) when there is no token", async () => {
    cookieStore.get.mockReturnValue(undefined);

    expect(await getCurrentUser()).toBeNull();
    expect(getAuthedSdkMock).not.toHaveBeenCalled();
  });

  it("returns null when the query fails (e.g. expired token) — never throws", async () => {
    cookieStore.get.mockReturnValue({ value: "stale-tok" });
    meQueryMock.mockRejectedValue(new Error("unauthorized"));

    expect(await getCurrentUser()).toBeNull();
  });
});

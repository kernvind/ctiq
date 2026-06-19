import { describe, it, expect, vi, beforeEach } from "vitest";

const { setAuthCookiesMock, redirectMock, loginMutationMock } = vi.hoisted(
  () => ({
    setAuthCookiesMock: vi.fn(),
    redirectMock: vi.fn(),
    loginMutationMock: vi.fn(),
  }),
);

vi.mock("@/lib/auth-cookies", () => ({ setAuthCookies: setAuthCookiesMock }));
vi.mock("next/navigation", () => ({ redirect: redirectMock }));
vi.mock("@repo/generated-schemas-web", () => ({
  sdk: { login_mutation: loginMutationMock },
}));

import { login } from "./actions";

function form(fields: Record<string, string>): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.set(k, v);
  return fd;
}

describe("login action", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns a validation error for invalid input and never calls the API", async () => {
    const res = await login(
      null,
      form({ username: "ab", password: "password123" }),
    );
    expect(res).toHaveProperty("error");
    expect(loginMutationMock).not.toHaveBeenCalled();
    expect(setAuthCookiesMock).not.toHaveBeenCalled();
  });

  it("sets cookies and redirects to /dashboard on success", async () => {
    loginMutationMock.mockResolvedValue({
      login: { accessToken: "a-tok", refreshToken: "r-tok" },
    });

    await login(null, form({ username: "alice", password: "password123" }));

    expect(loginMutationMock).toHaveBeenCalledWith({
      input: { username: "alice", password: "password123" },
    });
    expect(setAuthCookiesMock).toHaveBeenCalledWith("a-tok", "r-tok");
    expect(redirectMock).toHaveBeenCalledWith("/dashboard");
  });

  it("surfaces the GraphQL error message and does not set cookies", async () => {
    loginMutationMock.mockRejectedValue({
      response: { errors: [{ message: "Invalid credentials" }] },
    });

    const res = await login(
      null,
      form({ username: "alice", password: "password123" }),
    );

    expect(res).toEqual({ error: "Invalid credentials" });
    expect(setAuthCookiesMock).not.toHaveBeenCalled();
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when the error carries no GraphQL message", async () => {
    loginMutationMock.mockRejectedValue(new Error("network down"));
    const res = await login(
      null,
      form({ username: "alice", password: "password123" }),
    );
    expect(res).toEqual({ error: "Login failed" });
  });
});

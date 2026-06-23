import { describe, it, expect, vi, beforeEach } from "vitest";

const { getTrialMock, compareViewMock } = vi.hoisted(() => ({
  getTrialMock: vi.fn(),
  compareViewMock: vi.fn(),
}));

vi.mock("@/lib/actions/trial/details/actions", () => ({
  getTrial: getTrialMock,
}));
vi.mock("@/components/trial-compare-view", () => ({
  TrialCompareView: compareViewMock,
}));

// parseCompareIds (and its ZodNctIdSchema validation) is intentionally NOT mocked.
import Page from "./page";

const render = (ids?: string | string[]) =>
  Page({ searchParams: Promise.resolve({ ids }) });

// Flatten a React element's children to a plain string for message assertions.
function text(node: unknown): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(text).join("");
  const props = (node as { props?: { children?: unknown } }).props;
  return props ? text(props.children) : "";
}

describe("compare page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("prompts for more trials and never fetches when fewer than 2 valid ids", async () => {
    const result = await render("NCT00000001");

    expect(getTrialMock).not.toHaveBeenCalled();
    expect(result.type).not.toBe(compareViewMock);
    expect(text(result)).toContain("at least 2 trials");
  });

  it("renders the comparison view with all resolved trials", async () => {
    const a = { nct_id: "NCT00000001" };
    const b = { nct_id: "NCT00000002" };
    getTrialMock.mockResolvedValueOnce(a).mockResolvedValueOnce(b);

    const result = await render("NCT00000001,NCT00000002");

    expect(getTrialMock).toHaveBeenCalledTimes(2);
    expect(result.type).toBe(compareViewMock);
    expect(result.props.trials).toEqual([a, b]);
  });

  it("drops ids that resolve to null but still compares the rest", async () => {
    const a = { nct_id: "NCT00000001" };
    const c = { nct_id: "NCT00000003" };
    getTrialMock
      .mockResolvedValueOnce(a)
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(c);

    const result = await render("NCT00000001,NCT00000002,NCT00000003");

    expect(result.type).toBe(compareViewMock);
    expect(result.props.trials).toEqual([a, c]);
  });

  it("shows a not-found notice when too few selected trials resolve", async () => {
    getTrialMock
      .mockResolvedValueOnce({ nct_id: "NCT00000001" })
      .mockResolvedValueOnce(null);

    const result = await render("NCT00000001,NCT00000002");

    expect(result.type).not.toBe(compareViewMock);
    expect(text(result)).toContain("Not enough");
  });

  it("shows an inline error when a fetch throws", async () => {
    getTrialMock.mockRejectedValue(new Error("upstream down"));

    const result = await render("NCT00000001,NCT00000002");

    expect(result.type).not.toBe(compareViewMock);
    expect(text(result)).toContain("Could not load");
  });
});

"use client";

import { useState, useTransition, type Dispatch, type SetStateAction } from "react";
import { Plus, X, Loader2 } from "lucide-react";
import {
  addPortfolioTrialAction,
  removePortfolioTrialAction,
} from "@/lib/actions/portfolio/actions";

export type PortfolioEntry = { nctId: string };

const NCT_RE = /^NCT\d{8}$/;

/**
 * Manage the site's open-trial portfolio — the trials it's running and wants to enroll into.
 * The screening form matches patients against exactly this set. `entries` is owned by the
 * parent (lifted state) so the "Screen patient" button can react live to adds/removes;
 * updates are optimistic and reconciled by the server actions (which revalidate the route).
 */
export function PortfolioManager({
  entries,
  setEntries,
}: {
  entries: PortfolioEntry[];
  setEntries: Dispatch<SetStateAction<PortfolioEntry[]>>;
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();

  function add() {
    const nctId = draft.trim().toUpperCase();
    setError(null);
    if (!NCT_RE.test(nctId)) {
      setError("Enter a valid NCT id (e.g. NCT01234567).");
      return;
    }
    if (entries.some((e) => e.nctId === nctId)) {
      setDraft("");
      return; // already in the portfolio
    }
    setEntries((prev) => [{ nctId }, ...prev]);
    setDraft("");
    start(async () => {
      const res = await addPortfolioTrialAction(nctId);
      if (!res.ok) {
        setError(res.error);
        setEntries((prev) => prev.filter((e) => e.nctId !== nctId)); // revert
      }
    });
  }

  function remove(nctId: string) {
    const prev = entries;
    setEntries((p) => p.filter((e) => e.nctId !== nctId));
    start(async () => {
      const res = await removePortfolioTrialAction(nctId);
      if (!res.ok) {
        setError(res.error);
        setEntries(prev); // revert
      }
    });
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-3 px-6 pt-6">
      <div>
        <h2 className="text-lg font-semibold">Your open trials</h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          The studies your site is running. Patients are screened against this list.
        </p>
      </div>

      <div className="flex gap-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="Add an NCT id, e.g. NCT01234567"
          className="flex-1 rounded-md border px-2.5 py-1.5 text-sm"
        />
        <button
          onClick={add}
          disabled={pending}
          className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Add
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No trials yet — add the studies your site is running to screen patients against them.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {entries.map((e) => (
            <li
              key={e.nctId}
              className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-xs"
            >
              <span className="font-medium">{e.nctId}</span>
              <button
                onClick={() => remove(e.nctId)}
                className="text-muted-foreground hover:text-foreground"
                aria-label={`Remove ${e.nctId}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@repo/ui/lib/utils";
import { TrialCard } from "@/components/trial-card";
import { SaveLandscapeButton } from "@/components/save-landscape-button";
import { partitionByEnrollment } from "@/lib/trial-status";
import {
  buildCompareHref,
  MIN_COMPARE,
  MAX_COMPARE,
} from "@/lib/compare-ids";
import type { TrialCard as TrialCardType } from "@repo/generated-schemas-web";
import type { SearchState } from "@/lib/actions/trial/search/search-types";

/**
 * Results list for the master-detail search. Lives in the search *layout*, so it stays
 * mounted while the detail page swaps in `{children}` — opening a result or going back
 * never re-runs the search. It fetches (via the server action) only when the `?q=` query
 * itself changes. `basePath` is the route the cards link into ("/search" or
 * "/dashboard/trials").
 *
 * Trials no longer open for enrollment (completed/terminated/etc.) are hidden by default
 * so the list doesn't present non-actionable trials as if a patient could still join —
 * they stay one click away behind a toggle. See `lib/trial-status.ts`.
 */

export function TrialResultsList({
  basePath,
  state,
  query,
}: {
  basePath: string;
  state: SearchState | null;
  query: string;
}) {
  const pathname = usePathname();
  const [showClosed, setShowClosed] = useState(false);
  // Up to MAX_COMPARE trials selected for the side-by-side comparison (`/compare`).
  const [selected, setSelected] = useState<string[]>([]);

  const toggleSelected = (id: string) =>
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length >= MAX_COMPARE
          ? prev
          : [...prev, id],
    );

  if (!query) {
    return (
      <p className="py-8 text-center text-xs text-muted-foreground">
        Enter a description above to search trials.
      </p>
    );
  }

  if (state?.error) {
    return <p className="text-xs text-destructive">{state.error}</p>;
  }

  const results = state?.results ?? [];
  if (results.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No matching trials found. Try a different description.
      </p>
    );
  }

  const { open, closed } = partitionByEnrollment(results);
  // If nothing is open, fall back to showing the closed trials (with a notice) rather
  // than an empty list — there ARE matches, they're just not currently enrolling.
  const noneOpen = open.length === 0 && closed.length > 0;
  const closedVisible = showClosed || noneOpen;

  const renderCard = (trial: TrialCardType) => {
    const active = pathname === `${basePath}/${trial.nct_id}`;
    const checked = selected.includes(trial.nct_id);
    const atCap = selected.length >= MAX_COMPARE;
    return (
      <div key={trial.nct_id} className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={checked}
          disabled={!checked && atCap}
          onChange={() => toggleSelected(trial.nct_id)}
          aria-label={`Select ${trial.nct_id} to compare`}
          className="mt-3 h-4 w-4 shrink-0 accent-primary disabled:opacity-40"
        />
        <Link
          href={`${basePath}/${trial.nct_id}`}
          className={cn(
            "block min-w-0 flex-1 rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-ring",
            active ? "ring-2 ring-primary" : "hover:shadow-md",
          )}
        >
          <TrialCard trial={trial} />
        </Link>
      </div>
    );
  };

  // Saving a search as a landscape is an authed (dashboard) feature only.
  const isDashboard = basePath.startsWith("/dashboard");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {open.length} enrolling trial{open.length !== 1 ? "s" : ""}
          {closed.length > 0 ? ` · ${closed.length} not enrolling` : ""}
        </p>
        {isDashboard && <SaveLandscapeButton query={query} />}
      </div>

      {open.map(renderCard)}

      {noneOpen && (
        <p className="rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          None of these {closed.length} matching trial
          {closed.length !== 1 ? "s are" : " is"} currently enrolling.
        </p>
      )}

      {closed.length > 0 && !noneOpen && (
        <button
          type="button"
          onClick={() => setShowClosed((v) => !v)}
          className="self-start rounded-md px-2 py-1 text-xs font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          {closedVisible
            ? "Hide trials no longer enrolling"
            : `Show ${closed.length} trial${closed.length !== 1 ? "s" : ""} no longer enrolling`}
        </button>
      )}

      {closedVisible && (
        <div className="flex flex-col gap-3 opacity-75">
          {closed.map(renderCard)}
        </div>
      )}

      {selected.length >= MIN_COMPARE && (
        <div className="sticky bottom-2 z-10 mt-1 flex items-center justify-between gap-2 rounded-lg border bg-background/95 px-3 py-2 shadow-md backdrop-blur">
          <span className="text-xs text-muted-foreground">
            {selected.length} selected
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSelected([])}
              className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Clear
            </button>
            <Link
              href={buildCompareHref(selected)}
              className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition hover:bg-primary/90"
            >
              Compare ({selected.length})
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

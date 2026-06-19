"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { cn } from "@repo/ui/lib/utils";
import { TrialCard } from "@/components/trial-card";
import type { SearchState } from "@/lib/actions/trial/search/search-types";

/**
 * Results list for the master-detail search. Lives in the search *layout*, so it stays
 * mounted while the detail page swaps in `{children}` — opening a result or going back
 * never re-runs the search. It fetches (via the server action) only when the `?q=` query
 * itself changes. `basePath` is the route the cards link into ("/search" or
 * "/dashboard/trials").
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

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        {results.length} trial{results.length !== 1 ? "s" : ""} found
      </p>
      {results.map((trial) => {
        const active = pathname === `${basePath}/${trial.nct_id}`;
        return (
          <Link
            key={trial.nct_id}
            href={`${basePath}/${trial.nct_id}`}
            className={cn(
              "block rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-ring",
              active ? "ring-2 ring-primary" : "hover:shadow-md",
            )}
          >
            <TrialCard trial={trial} />
          </Link>
        );
      })}
    </div>
  );
}

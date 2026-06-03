"use client";

import { useActionState } from "react";
import { Button } from "@repo/ui/components/button";
import { Input } from "@repo/ui/components/input";
import { searchTrials, type SearchState } from "@/app/dashboard/trials/actions";
import { TrialCard } from "@/components/trial-card";
import { Search } from "lucide-react";

export function TrialSearchForm() {
  const [state, action, isPending] = useActionState<SearchState, FormData>(searchTrials, null);

  return (
    <div className="flex flex-col gap-6">
      <form action={action}>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
            <Input
              name="q"
              type="text"
              placeholder="Describe the condition, treatment, or patient profile… (10–500 chars)"
              defaultValue={state?.query ?? ""}
              className="pl-8"
              minLength={10}
              maxLength={500}
              required
              disabled={isPending}
            />
          </div>
          <Button type="submit" disabled={isPending}>
            {isPending ? "Searching…" : "Search"}
          </Button>
        </div>

        {state?.error && (
          <p className="mt-2 text-xs text-destructive">{state.error}</p>
        )}
      </form>

      {isPending && (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      )}

      {!isPending && state?.results && (
        <>
          <p className="text-xs text-muted-foreground">
            {state.results.length} trial{state.results.length !== 1 ? "s" : ""} found
          </p>
          <div className="flex flex-col gap-4">
            {state.results.map((trial) => (
              <TrialCard key={trial.nct_id} trial={trial} />
            ))}
          </div>
          {state.results.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No matching trials found. Try a different description.
            </p>
          )}
        </>
      )}
    </div>
  );
}

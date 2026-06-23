"use client";

import { useState, useTransition } from "react";
import { Bookmark, BookmarkCheck } from "lucide-react";
import { cn } from "@repo/ui/lib/utils";
import {
  saveTrialAction,
  unsaveTrialAction,
} from "@/lib/actions/trial/saved/actions";

/**
 * Toggle a trial in the current user's watchlist. Optimistic — flips immediately, then
 * reverts (and surfaces the error) if the server action fails.
 */
export function SaveTrialButton({
  nctId,
  initialSaved,
}: {
  nctId: string;
  initialSaved: boolean;
}) {
  const [saved, setSaved] = useState(initialSaved);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const toggle = () => {
    const next = !saved;
    setSaved(next);
    setError(null);
    startTransition(async () => {
      const res = next
        ? await saveTrialAction(nctId)
        : await unsaveTrialAction(nctId);
      if (!res.ok) {
        setSaved(!next);
        setError(res.error);
      }
    });
  };

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={pending}
      aria-pressed={saved}
      title={error ?? undefined}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium transition-colors disabled:opacity-60",
        saved
          ? "border-primary/30 bg-primary/10 text-primary"
          : "border-border text-muted-foreground hover:text-foreground",
      )}
    >
      {saved ? (
        <BookmarkCheck className="h-3.5 w-3.5" />
      ) : (
        <Bookmark className="h-3.5 w-3.5" />
      )}
      {saved ? "Saved" : "Save"}
    </button>
  );
}

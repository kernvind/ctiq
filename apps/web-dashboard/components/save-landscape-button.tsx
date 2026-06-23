"use client";

import { useState, useTransition } from "react";
import { Map, Check } from "lucide-react";
import { createLandscapeAction } from "@/lib/actions/landscape/actions";

/**
 * Save the current search query as a named, monitored landscape. No filter form — the
 * landscape is just this query, named; richer (agent) queries upgrade the same flow later.
 */
export function SaveLandscapeButton({ query }: { query: string }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const submit = () => {
    setError(null);
    startTransition(async () => {
      const res = await createLandscapeAction({
        name: name.trim() || query,
        q: query,
      });
      if (res.ok) {
        setDone(true);
        setOpen(false);
      } else {
        setError(res.error);
      }
    });
  };

  if (done) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Check className="h-3.5 w-3.5" /> Saved as landscape
      </span>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <Map className="h-3.5 w-3.5" /> Save as landscape
      </button>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="text"
        autoFocus
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name this landscape"
        className="h-7 rounded-md border border-input bg-input/20 px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring/30"
      />
      <button
        type="button"
        onClick={submit}
        disabled={pending}
        className="rounded-md bg-primary px-2.5 py-1 text-xs font-medium text-primary-foreground disabled:opacity-60"
      >
        {pending ? "Saving…" : "Save"}
      </button>
      <button
        type="button"
        onClick={() => setOpen(false)}
        className="text-xs text-muted-foreground hover:text-foreground"
      >
        Cancel
      </button>
      {error && <span className="text-xs text-destructive">{error}</span>}
    </div>
  );
}

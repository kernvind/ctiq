import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { getSavedTrials } from "@/lib/saved-trials";
import { getTrial } from "@/lib/actions/trial/details/actions";

export default async function SavedTrialsPage() {
  const saved = await getSavedTrials();

  if (saved.length === 0) {
    return (
      <div className="p-6">
        <div className="mx-auto max-w-3xl">
          <h2 className="text-lg font-semibold">Saved trials</h2>
          <p className="mt-6 rounded-lg border p-6 text-center text-sm text-muted-foreground">
            No saved trials yet. Open a trial and tap “Save” to add it here.
          </p>
        </div>
      </div>
    );
  }

  // Hydrate titles/status from the public trial query, best-effort per id.
  const rows = await Promise.all(
    saved.map(async (s) => {
      try {
        return { nctId: s.nctId, trial: await getTrial(s.nctId) };
      } catch {
        return { nctId: s.nctId, trial: null };
      }
    }),
  );

  return (
    <div className="p-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <h2 className="text-lg font-semibold">
          Saved trials{" "}
          <span className="text-sm font-normal text-muted-foreground">
            ({saved.length})
          </span>
        </h2>

        <div className="flex flex-col gap-2">
          {rows.map(({ nctId, trial }) => (
            <Link
              key={nctId}
              href={`/dashboard/trials/${nctId}`}
              className="flex items-center gap-3 rounded-lg border bg-background p-3 transition-colors hover:border-foreground/20"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {trial?.brief_title ?? trial?.official_title ?? nctId}
                </p>
                <p className="font-mono text-[11px] text-muted-foreground">
                  {nctId}
                  {trial?.overall_status ? ` · ${trial.overall_status}` : ""}
                </p>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

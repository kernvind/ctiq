import { notFound } from "next/navigation";
import Link from "next/link";
import { getLandscapes } from "@/lib/landscapes";
import { searchTrialsAction } from "@/lib/actions/trial/search/actions";
import { TrialCard } from "@/components/trial-card";
import { MarkSeenOnView } from "@/components/mark-seen-on-view";

export default async function LandscapeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const landscape = (await getLandscapes()).find((l) => l.id === id);
  if (!landscape) notFound();

  const state = await searchTrialsAction(landscape.spec.q);
  const results = state?.results ?? [];
  const seen = new Set(landscape.lastSeenNctIds);
  const firstCheck = !landscape.lastCheckedAt;
  const newCount = firstCheck
    ? 0
    : results.filter((r) => !seen.has(r.nct_id)).length;
  const currentIds = results.map((r) => r.nct_id);

  return (
    <div className="p-6">
      <div className="mx-auto flex max-w-3xl flex-col gap-4">
        <div>
          <Link
            href="/dashboard/landscapes"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            ← Landscapes
          </Link>
          <h2 className="mt-1 text-lg font-semibold">{landscape.name}</h2>
          <p className="text-xs text-muted-foreground">
            Monitoring: “{landscape.spec.q}”
            {landscape.spec.phase ? ` · ${landscape.spec.phase}` : ""}
          </p>
        </div>

        {state?.error ? (
          <p className="text-xs text-destructive">{state.error}</p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              {results.length} trial{results.length !== 1 ? "s" : ""}
              {firstCheck
                ? " · baseline saved"
                : newCount > 0
                  ? ` · ${newCount} new since last check`
                  : " · nothing new since last check"}
            </p>

            <div className="flex flex-col gap-3">
              {results.map((trial) => {
                const isNew = !firstCheck && !seen.has(trial.nct_id);
                return (
                  <Link
                    key={trial.nct_id}
                    href={`/dashboard/trials/${trial.nct_id}`}
                    className="relative block rounded-xl outline-none transition hover:shadow-md focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {isNew && (
                      <span className="absolute right-2 top-2 z-10 rounded bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
                        New
                      </span>
                    )}
                    <TrialCard trial={trial} />
                  </Link>
                );
              })}
            </div>

            {/* Record the current ids as seen, now that the delta is on screen. */}
            <MarkSeenOnView id={landscape.id} nctIds={currentIds} />
          </>
        )}
      </div>
    </div>
  );
}

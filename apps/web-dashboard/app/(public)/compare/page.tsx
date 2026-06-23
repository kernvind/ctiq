import { getTrial, type TrialDetail } from "@/lib/actions/trial/details/actions";
import { TrialCompareView } from "@/components/trial-compare-view";
import { parseCompareIds, MIN_COMPARE } from "@/lib/compare-ids";

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-6">
      <p className="mx-auto max-w-3xl rounded-lg border p-6 text-sm text-muted-foreground">
        {children}
      </p>
    </div>
  );
}

/**
 * Side-by-side trial comparison. URL-driven: `/compare?ids=NCT...,NCT...`. Async Server
 * Component following the trial-detail page pattern (parse + validate the params, fetch
 * via the unauthed `getTrial`, render a presentational view). Selection UI that builds
 * the `ids` list is a planned fast-follow.
 */
export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ ids?: string | string[] }>;
}) {
  const ids = parseCompareIds((await searchParams).ids);

  if (ids.length < MIN_COMPARE) {
    return (
      <Notice>
        Select at least {MIN_COMPARE} trials to compare them side by side.
      </Notice>
    );
  }

  let trials: TrialDetail[];
  try {
    const fetched = await Promise.all(ids.map((id) => getTrial(id)));
    trials = fetched.filter((t): t is TrialDetail => t != null);
  } catch {
    return (
      <Notice>
        Could not load these trials right now. Please try again.
      </Notice>
    );
  }

  if (trials.length < MIN_COMPARE) {
    return (
      <Notice>
        Not enough of the selected trials could be found to compare.
      </Notice>
    );
  }

  return <TrialCompareView trials={trials} />;
}

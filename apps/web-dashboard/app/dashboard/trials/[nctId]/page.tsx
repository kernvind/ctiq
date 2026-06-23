import { notFound } from "next/navigation";
import { getTrial } from "@/lib/actions/trial/details/actions";
import { getSavedTrials } from "@/lib/saved-trials";
import { TrialDetailView } from "@/components/trial-detail-view";
import { SaveTrialButton } from "@/components/save-trial-button";

import { ZodNctIdSchema } from "@repo/zod-validations";

export default async function DashboardTrialDetailPage({
  params,
}: {
  params: Promise<{ nctId: string }>;
}) {
  const parsed = ZodNctIdSchema.safeParse((await params).nctId);

  if (!parsed.success) notFound();
  const nctId = parsed.data.toUpperCase();

  let trial;
  let saved;
  try {
    [trial, saved] = await Promise.all([getTrial(nctId), getSavedTrials()]);
  } catch {
    return (
      <p className="rounded-lg border p-6 text-sm text-destructive">
        Could not load this trial right now. Please try again.
      </p>
    );
  }

  if (!trial) notFound();

  const isSaved = saved.some((s) => s.nctId === nctId);

  return (
    <TrialDetailView
      trial={trial}
      actions={<SaveTrialButton nctId={nctId} initialSaved={isSaved} />}
    />
  );
}

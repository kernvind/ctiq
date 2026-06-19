import { notFound } from "next/navigation";
import { getTrial } from "@/lib/actions/trial/details/actions";
import { TrialDetailView } from "@/components/trial-detail-view";

import { ZodNctIdSchema } from "@repo/zod-validations";

export default async function SearchTrialDetailPage({
  params,
}: {
  params: Promise<{ nctId: string }>;
}) {
  const parsed = ZodNctIdSchema.safeParse((await params).nctId);

  if (!parsed.success) notFound();

  let trial;

  try {
    trial = await getTrial(parsed.data);
  } catch {
    return (
      <p className="rounded-lg border p-6 text-sm text-destructive">
        Could not load this trial right now. Please try again.
      </p>
    );
  }

  if (!trial) notFound();

  return <TrialDetailView trial={trial} />;
}

"use server";

import { revalidatePath } from "next/cache";
import { withAuthedSdk } from "@/lib/authed-sdk";

export type PortfolioResult = { ok: true } | { ok: false; error: string };

function messageOf(err: unknown): string {
  return (
    (err as { response?: { errors?: { message: string }[] } })?.response
      ?.errors?.[0]?.message ?? "Something went wrong. Please try again."
  );
}

/** Add a trial to the current user's open-trial portfolio. Idempotent server-side. */
export async function addPortfolioTrialAction(
  nctId: string,
): Promise<PortfolioResult> {
  try {
    await withAuthedSdk((sdk) => sdk.addPortfolioTrial_mutation({ nctId }));
    revalidatePath("/dashboard/screen");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

/** Remove a trial from the current user's portfolio. */
export async function removePortfolioTrialAction(
  nctId: string,
): Promise<PortfolioResult> {
  try {
    await withAuthedSdk((sdk) => sdk.removePortfolioTrial_mutation({ nctId }));
    revalidatePath("/dashboard/screen");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

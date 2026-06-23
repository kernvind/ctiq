"use server";

import { withAuthedSdk } from "@/lib/authed-sdk";

export type SaveResult = { ok: true } | { ok: false; error: string };

function messageOf(err: unknown): string {
  return (
    (err as { response?: { errors?: { message: string }[] } })?.response
      ?.errors?.[0]?.message ?? "Something went wrong. Please try again."
  );
}

/** Save a trial to the current user's watchlist. Idempotent server-side. */
export async function saveTrialAction(nctId: string): Promise<SaveResult> {
  try {
    await withAuthedSdk((sdk) => sdk.saveTrial_mutation({ nctId }));
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

/** Remove a trial from the current user's watchlist. */
export async function unsaveTrialAction(nctId: string): Promise<SaveResult> {
  try {
    await withAuthedSdk((sdk) => sdk.unsaveTrial_mutation({ nctId }));
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

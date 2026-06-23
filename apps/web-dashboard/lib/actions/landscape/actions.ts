"use server";

import { withAuthedSdk } from "@/lib/authed-sdk";
import { flattenZodErrors } from "@/lib/zod-errors";
import { ZodCreateLandscapeSchema } from "@repo/zod-validations";

export type LandscapeResult = { ok: true } | { ok: false; error: string };

function messageOf(err: unknown): string {
  return (
    (err as { response?: { errors?: { message: string }[] } })?.response
      ?.errors?.[0]?.message ?? "Something went wrong. Please try again."
  );
}

/** Save the current search as a named, monitored landscape. */
export async function createLandscapeAction(input: {
  name: string;
  q: string;
  phase?: string;
}): Promise<LandscapeResult> {
  const parsed = ZodCreateLandscapeSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: flattenZodErrors(parsed.error) };
  }
  try {
    await withAuthedSdk((sdk) =>
      sdk.createLandscape_mutation({ input: parsed.data }),
    );
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

export async function deleteLandscapeAction(
  id: string,
): Promise<LandscapeResult> {
  try {
    await withAuthedSdk((sdk) => sdk.deleteLandscape_mutation({ id }));
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

/** Update a landscape's monitoring snapshot to the ids just seen (called on view). */
export async function markLandscapeSeenAction(
  id: string,
  nctIds: string[],
): Promise<LandscapeResult> {
  try {
    await withAuthedSdk((sdk) =>
      sdk.markLandscapeSeen_mutation({ id, nctIds }),
    );
    return { ok: true };
  } catch (err) {
    return { ok: false, error: messageOf(err) };
  }
}

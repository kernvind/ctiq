import { sdk } from "@repo/generated-schemas-web";
import type { Trial_QueryQuery } from "@repo/generated-schemas-web";

/** A fully-loaded trial (the non-null result of the `trial` query). */
export type TrialDetail = NonNullable<Trial_QueryQuery["trial"]>;

/**
 * Fetch a trial's full record by NCT id. Uses the unauthed `sdk` — `trial` is a public
 * query — so this works for both the public and dashboard detail pages. Returns null when
 * the id has no matching trial; throws on transport/backend errors (caller handles).
 */
export async function getTrial(nctId: string): Promise<TrialDetail | null> {
  const data = await sdk.trial_query({ nctId: nctId.toUpperCase() });
  return data.trial ?? null;
}

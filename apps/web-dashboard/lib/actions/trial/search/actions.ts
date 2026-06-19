"use server";

import { ZodTrialSearchSchema } from "@repo/zod-validations";
import { sdk } from "@repo/generated-schemas-web";
import { flattenZodErrors } from "@/lib/zod-errors";
import type { SearchState } from "@/lib/actions/trial/search/search-types";

/**
 * Trial search server action. Invoked from the client results list (which lives in the
 * persistent search layout and reads the query from the URL), so results stay mounted
 * across detail navigation. Uses the unauthed `sdk` — `searchTrials` has no auth guard —
 * so the same action backs both the public (/search) and dashboard (/dashboard/trials)
 * surfaces.
 */
export async function searchTrialsAction(
  rawQuery: string,
): Promise<SearchState> {
  const result = ZodTrialSearchSchema.safeParse({ q: rawQuery });
  if (!result.success) {
    return { error: flattenZodErrors(result.error), query: rawQuery };
  }

  try {
    const data = await sdk.searchTrials_query({ q: { q: result.data.q } });
    return { results: data.searchTrials, query: result.data.q };
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Search failed. Please try again.";
    return { error: message, query: result.data.q };
  }
}

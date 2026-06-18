"use server";

import { ZodTrialSearchSchema } from "@repo/zod-validations";
import { flattenZodErrors } from "@/lib/zod-errors";
import { withAuthedSdk } from "@/lib/authed-sdk";
import type { TrialCard } from "@repo/generated-schemas-web";

export type SearchState = {
  error?: string;
  results?: TrialCard[];
  query?: string;
} | null;

export async function searchTrials(
  _prevState: SearchState,
  formData: FormData,
): Promise<SearchState> {
  const rawQuery = formData.get("q");

  const result = ZodTrialSearchSchema.safeParse({ q: rawQuery });
  if (!result.success) {
    return { error: flattenZodErrors(result.error), query: String(rawQuery ?? "") };
  }

  try {
    // Auto-refreshes the access token (rotating the refresh token) and retries once
    // if the call fails with an auth error.
    const data = await withAuthedSdk((sdk) =>
      sdk.searchTrials_query({ q: { q: result.data.q } }),
    );
    return { results: data.searchTrials, query: result.data.q };
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Search failed. Please try again.";
    return { error: message, query: result.data.q };
  }
}

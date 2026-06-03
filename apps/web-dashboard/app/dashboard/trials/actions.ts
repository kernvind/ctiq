"use server";

import { cookies } from "next/headers";
import { getAuthedSdk } from "@repo/generated-schemas-web";
import { ZodTrialSearchSchema } from "@repo/zod-validations";
import { flattenZodErrors } from "@/lib/zod-errors";
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

  const cookieStore = await cookies();
  const token = cookieStore.get("token")?.value;

  try {
    const sdk = token ? getAuthedSdk(token) : (await import("@repo/generated-schemas-web")).sdk;
    const data = await sdk.searchTrials_query({ q: { q: result.data.q } });
    return { results: data.searchTrials, query: result.data.q };
  } catch (err: unknown) {
    const message =
      (err as { response?: { errors?: { message: string }[] } })?.response
        ?.errors?.[0]?.message ?? "Search failed. Please try again.";
    return { error: message, query: result.data.q };
  }
}

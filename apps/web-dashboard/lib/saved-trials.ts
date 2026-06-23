import { cookies } from "next/headers";
import {
  getAuthedSdk,
  type SavedTrials_QueryQuery,
} from "@repo/generated-schemas-web";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export type SavedTrial = SavedTrials_QueryQuery["savedTrials"][number];

/**
 * The current user's saved trials. Read-only — reads the access token and does NOT
 * refresh (no cookie writes), so it's safe in Server Components/layouts. Returns [] when
 * unauthenticated or the token is rejected (chrome degrades, never errors).
 */
export async function getSavedTrials(): Promise<SavedTrial[]> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) return [];
  try {
    const data = await getAuthedSdk(token).savedTrials_query();
    return data.savedTrials ?? [];
  } catch {
    return [];
  }
}

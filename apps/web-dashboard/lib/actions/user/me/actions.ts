import { cookies } from "next/headers";
import { getAuthedSdk, type Me_QueryQuery } from "@repo/generated-schemas-web";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

/** The authenticated user as returned by the `me` query. */
export type CurrentUser = Me_QueryQuery["me"];

/**
 * Fetch the current user for chrome/personalization. Read-only — it reads the access
 * token from cookies and does NOT refresh (so it never writes cookies), which makes it
 * safe to call from Server Components/layouts. Returns null when there's no token or the
 * token is rejected; callers degrade gracefully rather than treating this as fatal.
 */
export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) return null;
  try {
    const data = await getAuthedSdk(token).me_query();
    return data.me ?? null;
  } catch {
    return null;
  }
}

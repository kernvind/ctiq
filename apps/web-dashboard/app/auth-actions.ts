"use server";

import { sdk } from "@repo/generated-schemas-web";
import {
  getRefreshToken,
  setAuthCookies,
  clearAuthCookies,
} from "@/lib/auth-cookies";

/**
 * Exchange the refresh token for a fresh access + refresh token (rotation) and update
 * the cookies. Returns false (and clears cookies) if the refresh token is missing or
 * rejected — the caller should then treat the user as logged out.
 *
 * Must run in a Server Action / Route Handler context (it sets cookies).
 */
export async function refreshSession(): Promise<boolean> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return false;
  try {
    const data = await sdk.refresh_mutation({ refreshToken });
    await setAuthCookies(data.refresh.accessToken, data.refresh.refreshToken);
    return true;
  } catch {
    await clearAuthCookies();
    return false;
  }
}

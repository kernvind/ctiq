"use server";

import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import {
  getRefreshToken,
  setAuthCookies,
  clearAuthCookies,
} from "@/lib/auth-cookies";

/** Revoke the current session server-side and clear cookies, then go to /login. */
export async function logout() {
  const refreshToken = await getRefreshToken();
  if (refreshToken) {
    try {
      await sdk.logout_mutation({ refreshToken });
    } catch {
      // Best-effort server-side revoke; clear local cookies regardless.
    }
  }
  await clearAuthCookies();
  redirect("/login");
}

/**
 * Exchange the refresh token for a fresh access + refresh token (rotation) and update
 * the cookies. Returns false (and clears cookies) if the refresh token is missing or
 * rejected — the caller should then treat the user as logged out.
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

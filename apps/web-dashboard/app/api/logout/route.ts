import { redirect } from "next/navigation";
import { sdk } from "@repo/generated-schemas-web";
import { getRefreshToken, clearAuthCookies } from "@/lib/auth-cookies";

export async function POST() {
  // Revoke the session server-side (best effort) before clearing local cookies, so the
  // refresh token can't be reused even if it leaked.
  const refreshToken = await getRefreshToken();
  if (refreshToken) {
    try {
      await sdk.logout_mutation({ refreshToken });
    } catch {
      // Clear cookies regardless of server-side revoke outcome.
    }
  }
  await clearAuthCookies();
  // Land on the public home (anonymous users can still search), not the login page.
  redirect("/");
}

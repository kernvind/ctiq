import { cookies } from "next/headers";

// Access token keeps the existing name (`token`) — other code (e.g. the route
// redirect) already reads it. The refresh token gets its own cookie.
export const ACCESS_TOKEN_COOKIE = "token";
export const REFRESH_TOKEN_COOKIE = "refresh_token";

// Matches the server's REFRESH_TOKEN_TTL_DAYS default (30d) so the cookie outlives
// short access tokens and survives browser restarts.
const REFRESH_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;

function baseCookieOptions() {
  return {
    httpOnly: true,
    // COOKIE_SECURE=true only when served over HTTPS (staging/prod). NODE_ENV is the
    // wrong signal — local Docker is HTTP.
    secure: process.env.COOKIE_SECURE === "true",
    sameSite: "lax" as const,
    path: "/",
  };
}

export async function setAuthCookies(accessToken: string, refreshToken: string) {
  const store = await cookies();
  store.set(ACCESS_TOKEN_COOKIE, accessToken, baseCookieOptions());
  store.set(REFRESH_TOKEN_COOKIE, refreshToken, {
    ...baseCookieOptions(),
    maxAge: REFRESH_MAX_AGE_SECONDS,
  });
}

export async function clearAuthCookies() {
  const store = await cookies();
  store.delete(ACCESS_TOKEN_COOKIE);
  store.delete(REFRESH_TOKEN_COOKIE);
}

export async function getRefreshToken(): Promise<string | undefined> {
  const store = await cookies();
  return store.get(REFRESH_TOKEN_COOKIE)?.value;
}

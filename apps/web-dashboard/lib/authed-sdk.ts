import { cookies } from "next/headers";
import { getAuthedSdk } from "@repo/generated-schemas-web";
import { ACCESS_TOKEN_COOKIE } from "./auth-cookies";
import { refreshSession } from "@/app/auth-actions";

type AuthedSdk = ReturnType<typeof getAuthedSdk>;

function isAuthError(err: unknown): boolean {
  const response = (
    err as {
      response?: {
        status?: number;
        errors?: Array<{ message?: string; extensions?: { code?: string } }>;
      };
    }
  )?.response;
  if (response?.status === 401) return true;
  return (
    response?.errors?.some(
      (e) =>
        e?.extensions?.code === "UNAUTHENTICATED" ||
        /unauthor|token expired|jwt/i.test(e?.message ?? ""),
    ) ?? false
  );
}

/**
 * Run an authenticated GraphQL call using the access token from cookies. If it fails
 * with an auth error (expired/invalid access token), transparently refresh the token
 * (which rotates the refresh token) and retry once. If the refresh fails, the original
 * error is rethrown and the user is effectively logged out (cookies cleared).
 *
 * Must be called from a Server Action or Route Handler — it may set cookies.
 */
export async function withAuthedSdk<T>(
  fn: (sdk: AuthedSdk) => Promise<T>,
): Promise<T> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  try {
    return await fn(getAuthedSdk(token ?? ""));
  } catch (err) {
    if (!isAuthError(err)) throw err;

    const refreshed = await refreshSession();
    if (!refreshed) throw err;

    const newToken = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
    return await fn(getAuthedSdk(newToken ?? ""));
  }
}

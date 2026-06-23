import { cookies } from "next/headers";
import {
  getAuthedSdk,
  type Landscapes_QueryQuery,
} from "@repo/generated-schemas-web";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export type Landscape = Landscapes_QueryQuery["landscapes"][number];

/**
 * The current user's saved landscapes. Read-only (no token refresh / cookie writes), so
 * it's safe in Server Components. Returns [] when unauthenticated or the token is rejected.
 */
export async function getLandscapes(): Promise<Landscape[]> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) return [];
  try {
    const data = await getAuthedSdk(token).landscapes_query();
    return data.landscapes ?? [];
  } catch {
    return [];
  }
}

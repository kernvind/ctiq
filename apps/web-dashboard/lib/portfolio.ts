import { cookies } from "next/headers";
import {
  getAuthedSdk,
  type Portfolio_QueryQuery,
} from "@repo/generated-schemas-web";
import { ACCESS_TOKEN_COOKIE } from "@/lib/auth-cookies";

export type PortfolioTrial = Portfolio_QueryQuery["portfolio"][number];

/**
 * The current user's open-trial portfolio (the trials their site is running). Read-only —
 * reads the access token and does NOT refresh (no cookie writes), so it's safe in Server
 * Components/layouts. Returns [] when unauthenticated or the token is rejected.
 */
export async function getPortfolio(): Promise<PortfolioTrial[]> {
  const token = (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value;
  if (!token) return [];
  try {
    const data = await getAuthedSdk(token).portfolio_query();
    return data.portfolio ?? [];
  } catch {
    return [];
  }
}

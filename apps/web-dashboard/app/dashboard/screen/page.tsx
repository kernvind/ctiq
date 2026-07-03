import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/actions/user/me/actions";
import { getPortfolio } from "@/lib/portfolio";
import { PortfolioScreen } from "@/features/portfolio/portfolio-screen";

/**
 * Portfolio screening (site-payer wedge): manage the site's open-trial portfolio and screen a
 * patient against it at the point of care. Gated to the CLINICIAN role (the api-core resolver
 * also enforces it — this is UX, not the security boundary). No PHI: the profile is evaluated
 * in-request and never stored.
 */
export default async function ScreenPage() {
  const user = await getCurrentUser();
  if (user?.role !== "CLINICIAN") {
    redirect("/dashboard");
  }
  const portfolio = await getPortfolio();
  return (
    <PortfolioScreen initialPortfolio={portfolio.map((p) => ({ nctId: p.nctId }))} />
  );
}

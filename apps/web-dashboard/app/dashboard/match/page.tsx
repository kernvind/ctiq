import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/actions/user/me/actions";
import { MatchView } from "@/features/eligibility-match/match-view";

/**
 * Eligibility matcher — clinician decision support (ROADMAP step 6). Gated to the CLINICIAN
 * role: non-clinicians are redirected. (The api-core resolver also enforces the role, so
 * this is UX, not the security boundary.)
 */
export default async function MatchPage() {
  const user = await getCurrentUser();
  if (user?.role !== "CLINICIAN") {
    redirect("/dashboard");
  }
  return <MatchView />;
}

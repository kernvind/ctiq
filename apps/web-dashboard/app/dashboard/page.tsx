import Link from "next/link";
import { Sparkles, Bookmark, Bell, ArrowRight } from "lucide-react";
import { getCurrentUser } from "@/lib/actions/user/me/actions";
import { getSavedTrials } from "@/lib/saved-trials";
import { roleLabel } from "@/lib/role";

// Role-specific cards. Each is either live today or an honestly-flagged upcoming
// feature (the AI/agent roadmap). Keyed by the @repo/db Role values.
const ROLE_PANEL: Record<string, { label: string; soon?: string }[]> = {
  PATIENT: [
    { label: "Trials you may be eligible for", soon: "Soon" },
    { label: "Eligibility assistant", soon: "AI" },
  ],
  CLINICIAN: [
    { label: "Comparison sets", soon: "Soon" },
    { label: "Plain-language summaries", soon: "AI" },
  ],
  ANALYST: [
    { label: "Saved landscapes", soon: "Soon" },
    { label: "Competitor digest", soon: "Agent" },
  ],
  ADMIN: [
    { label: "Pipeline health", soon: "Soon" },
    { label: "User management", soon: "Soon" },
  ],
};

function SoonBadge({ kind }: { kind: string }) {
  return (
    <span className="inline-flex items-center rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
      {kind} · soon
    </span>
  );
}

export default async function DashboardPage() {
  const [user, saved] = await Promise.all([
    getCurrentUser(),
    getSavedTrials(),
  ]);
  const role = user?.role ?? "PATIENT";
  const panel = ROLE_PANEL[role] ?? ROLE_PANEL.PATIENT;

  return (
    <div className="p-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-5">
        <div>
          <h2 className="text-lg font-semibold">
            Welcome back{user?.name ? `, ${user.name}` : ""}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {roleLabel(role) || "Your"} workspace
          </p>
        </div>

        {/* Ask bar — semantic search today; the future LLM/agent entry point. */}
        <Link
          href="/dashboard/trials"
          className="flex items-center gap-2.5 rounded-xl border bg-background px-3.5 py-3 transition-colors hover:border-foreground/20"
        >
          <Sparkles className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            Ask CTIQ — search trials, compare…
          </span>
          <span className="ml-auto">
            <SoonBadge kind="AI" />
          </span>
        </Link>

        <div className="grid gap-3 sm:grid-cols-2">
          {/* Saved trials — live today. */}
          <Link
            href="/dashboard/saved"
            className="rounded-lg border bg-background p-4 transition-colors hover:border-foreground/20"
          >
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Bookmark className="h-4 w-4" />
              <span>Saved trials</span>
            </div>
            <div className="mt-1.5 flex items-center justify-between">
              <span className="text-2xl font-medium">{saved.length}</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>
          </Link>

          {/* Role-specific roadmap cards. */}
          {panel.map((c) => (
            <div
              key={c.label}
              className="rounded-lg border bg-background p-4 opacity-90"
            >
              <p className="text-xs text-muted-foreground">{c.label}</p>
              {c.soon && (
                <div className="mt-2">
                  <SoonBadge kind={c.soon} />
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Activity feed — the agent surface; empty scaffold for now. */}
        <div className="rounded-lg border bg-background p-4">
          <div className="mb-2 flex items-center gap-2">
            <Bell className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-medium">Activity</span>
            <SoonBadge kind="Agent" />
          </div>
          <p className="text-xs text-muted-foreground">
            Monitoring and alerts will appear here once you save landscapes and
            trials to watch.
          </p>
        </div>
      </div>
    </div>
  );
}

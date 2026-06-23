"use client";
import { useRouter } from "next/navigation";

import { Button } from "@repo/ui/components/button";
import { Fragment } from "react";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { rigorBadges } from "@/lib/trial-rigor";
import { formatAgeRange } from "@/lib/format-age";
import type { TrialDetail } from "@/lib/actions/trial/details/actions";

const STATUS_COLORS: Record<string, string> = {
  RECRUITING:
    "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  COMPLETED: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  ACTIVE_NOT_RECRUITING:
    "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  TERMINATED: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  WITHDRAWN: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

function StatusBadge({ status }: { status?: string | null }) {
  if (!status) return <span className="text-muted-foreground">—</span>;
  const classes =
    STATUS_COLORS[status.toUpperCase().replace(/ /g, "_")] ??
    "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}
    >
      {status}
    </span>
  );
}

function primaryOutcome(trial: TrialDetail): string {
  const measures = (trial.outcomes ?? [])
    .filter((o) => (o.outcome_type ?? "").toUpperCase() === "PRIMARY")
    .map((o) => o.measure)
    .filter(Boolean);
  return measures.slice(0, 2).join("; ");
}

const DASH = <span className="text-muted-foreground">—</span>;

// Each comparison row: a label and how to render one trial's value for it. Driving the
// grid off a config keeps every trial column rendering the exact same ordered attributes.
const ROWS: { label: string; render: (t: TrialDetail) => React.ReactNode }[] = [
  { label: "Status", render: (t) => <StatusBadge status={t.overall_status} /> },
  {
    label: "Phase",
    render: (t) =>
      t.phases && t.phases.length > 0 ? t.phases.join(", ") : DASH,
  },
  {
    label: "Design",
    render: (t) => {
      const r = rigorBadges(t);
      return r.length > 0 ? r.join(" · ") : DASH;
    },
  },
  { label: "Sponsor", render: (t) => t.lead_sponsor_name || DASH },
  {
    label: "Enrollment",
    render: (t) =>
      t.enrollment_count != null ? t.enrollment_count.toLocaleString() : DASH,
  },
  { label: "Sex", render: (t) => t.sex || DASH },
  {
    label: "Age",
    render: (t) =>
      formatAgeRange(
        { raw: t.min_age_raw, years: t.min_age_years },
        { raw: t.max_age_raw, years: t.max_age_years },
      ) || DASH,
  },
  {
    label: "Healthy volunteers",
    render: (t) =>
      t.healthy_volunteers == null ? DASH : t.healthy_volunteers ? "Yes" : "No",
  },
  {
    label: "Primary outcome",
    render: (t) => primaryOutcome(t) || DASH,
  },
];

/**
 * Presentational side-by-side comparison: trials in columns, attributes in aligned rows.
 * Pure Server Component (no client interactivity) — selection happens upstream via the
 * `?ids=` URL, see `app/(public)/compare/page.tsx`.
 */
export function TrialCompareView({ trials }: { trials: TrialDetail[] }) {
  const router = useRouter();
  return (
    <div className="p-6">
      <div className="mx-auto max-w-5xl">
        <Button
          variant="link"
          className="gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
          onClick={() => router.back()}
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to search
        </Button>
        <h1 className="mb-4 text-sm font-semibold">
          Comparing {trials.length} trials
        </h1>

        <div className="overflow-x-auto">
          <div
            className="grid min-w-fit gap-px rounded-lg bg-border text-xs"
            style={{
              gridTemplateColumns: `minmax(8rem, max-content) repeat(${trials.length}, minmax(12rem, 1fr))`,
            }}
          >
            {/* Header row: corner cell + one title cell per trial */}
            <div className="bg-background p-2" />
            {trials.map((t) => (
              <div key={t.nct_id} className="bg-background p-2">
                <p className="font-semibold leading-snug line-clamp-3">
                  {t.brief_title ?? t.official_title ?? "(untitled trial)"}
                </p>
                <a
                  href={`https://clinicaltrials.gov/study/${t.nct_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 font-mono text-[10px] text-primary hover:underline"
                >
                  {t.nct_id} <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </div>
            ))}

            {/* Attribute rows */}
            {ROWS.map((row) => (
              <Fragment key={row.label}>
                <div className="bg-muted/40 p-2 font-medium uppercase tracking-wide text-[10px] text-muted-foreground">
                  {row.label}
                </div>
                {trials.map((t) => (
                  <div key={t.nct_id} className="bg-background p-2">
                    {row.render(t)}
                  </div>
                ))}
              </Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

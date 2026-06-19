"use client";
import { useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@repo/ui/components/card";
import { Button } from "@repo/ui/components/button";
import type { TrialDetail } from "@/lib/get-trial";

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
  if (!status) return null;
  const classes =
    STATUS_COLORS[status.toUpperCase().replace(/ /g, "_")] ??
    "bg-muted text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium ${classes}`}
    >
      {status}
    </span>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      {children}
    </span>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm">{children}</CardContent>
    </Card>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value?: string | number | null;
}) {
  if (value == null || value === "") return null;
  return (
    <div>
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xs">{value}</p>
    </div>
  );
}

/**
 * Presentational full-trial view, rendered in the detail pane of the master-detail search.
 * `backHref` renders an optional "back to search" link (omit it when the results list is
 * already on screen).
 */
export function TrialDetailView({ trial }: { trial: TrialDetail }) {
  const ageRange = [
    trial.min_age_years != null ? `${trial.min_age_years}y` : null,
    trial.max_age_years != null ? `${trial.max_age_years}y` : null,
  ]
    .filter(Boolean)
    .join(" – ");

  const ctGovUrl = `https://clinicaltrials.gov/study/${trial.nct_id}`;
  const router = useRouter();
  return (
    <div className="p-6">
      <div className="max-w-3xl mx-auto flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <Button
            variant="link"
            className="gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
            onClick={() => router.back()}
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to search
          </Button>

          <a
            href={ctGovUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            ClinicalTrials.gov <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        {/* Header */}
        <Card>
          <CardHeader className="border-b pb-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                <CardTitle className="text-base font-semibold leading-snug">
                  {trial.brief_title ??
                    trial.official_title ??
                    "(untitled trial)"}
                </CardTitle>
                <p className="mt-1 font-mono text-xs text-muted-foreground">
                  {trial.nct_id}
                </p>
              </div>
              <StatusBadge status={trial.overall_status} />
            </div>
            {trial.phases && trial.phases.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {trial.phases.map((p) => (
                  <Badge key={p}>{p}</Badge>
                ))}
              </div>
            )}
          </CardHeader>
          <CardContent className="grid gap-3 pt-3 sm:grid-cols-2">
            <Field label="Sponsor" value={trial.lead_sponsor_name} />
            <Field label="Organization" value={trial.organization} />
            <Field label="Study type" value={trial.study_type} />
            <Field
              label="Enrollment"
              value={
                trial.enrollment_count != null
                  ? `${trial.enrollment_count}${trial.enrollment_type ? ` (${trial.enrollment_type})` : ""}`
                  : null
              }
            />
          </CardContent>
        </Card>

        {trial.brief_summary && (
          <Section title="Summary">
            <p className="whitespace-pre-line text-xs leading-relaxed">
              {trial.brief_summary}
            </p>
          </Section>
        )}

        {trial.conditions && trial.conditions.length > 0 && (
          <Section title="Conditions">
            <div className="flex flex-wrap gap-1">
              {trial.conditions.map((c) => (
                <Badge key={c}>{c}</Badge>
              ))}
            </div>
          </Section>
        )}

        <Section title="Eligibility">
          <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            {trial.sex && <span>Sex: {trial.sex}</span>}
            {ageRange && <span>Age: {ageRange}</span>}
            {trial.healthy_volunteers != null && (
              <span>
                Healthy volunteers: {trial.healthy_volunteers ? "Yes" : "No"}
              </span>
            )}
          </div>
          {trial.eligibility_criteria && (
            <p className="whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
              {trial.eligibility_criteria}
            </p>
          )}
        </Section>

        {trial.interventions && trial.interventions.length > 0 && (
          <Section title="Interventions">
            <ul className="space-y-2">
              {trial.interventions.map((iv, i) => (
                <li key={i} className="text-xs">
                  <span className="font-medium">{iv.name}</span>
                  {iv.type && (
                    <span className="text-muted-foreground"> · {iv.type}</span>
                  )}
                  {iv.description && (
                    <p className="text-[11px] text-muted-foreground">
                      {iv.description}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {trial.outcomes && trial.outcomes.length > 0 && (
          <Section title="Outcomes">
            <ul className="space-y-2">
              {trial.outcomes.map((o, i) => (
                <li key={i} className="text-xs">
                  {o.outcome_type && <Badge>{o.outcome_type}</Badge>}{" "}
                  <span className="font-medium">{o.measure}</span>
                  {o.time_frame && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {o.time_frame}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}

        {trial.locations && trial.locations.length > 0 && (
          <Section title={`Locations (${trial.locations.length})`}>
            <ul className="space-y-1.5">
              {trial.locations.map((loc, i) => (
                <li
                  key={i}
                  className="flex items-start justify-between gap-2 text-xs"
                >
                  <span>
                    {loc.facility ?? "—"}
                    <span className="text-muted-foreground">
                      {" "}
                      {[loc.city, loc.state, loc.country]
                        .filter(Boolean)
                        .join(", ")}
                    </span>
                  </span>
                  <StatusBadge status={loc.status} />
                </li>
              ))}
            </ul>
          </Section>
        )}

        {trial.officials && trial.officials.length > 0 && (
          <Section title="Officials">
            <ul className="space-y-1 text-xs">
              {trial.officials.map((off, i) => (
                <li key={i}>
                  <span className="font-medium">{off.name}</span>
                  {off.role && (
                    <span className="text-muted-foreground"> · {off.role}</span>
                  )}
                  {off.affiliation && (
                    <span className="text-muted-foreground">
                      {" "}
                      — {off.affiliation}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        )}
      </div>
    </div>
  );
}

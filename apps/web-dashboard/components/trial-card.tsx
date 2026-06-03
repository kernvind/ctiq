import type { TrialCard as TrialCardType } from "@repo/generated-schemas-web";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@repo/ui/components/card";

const STATUS_COLORS: Record<string, string> = {
  RECRUITING: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  COMPLETED: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  ACTIVE_NOT_RECRUITING: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
  TERMINATED: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  WITHDRAWN: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase().replace(/ /g, "_");
  const classes = STATUS_COLORS[normalized] ?? "bg-muted text-muted-foreground";
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium ${classes}`}>
      {status}
    </span>
  );
}

function PhaseBadge({ phase }: { phase: string }) {
  return (
    <span className="inline-flex items-center rounded border border-border px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
      {phase}
    </span>
  );
}

export function TrialCard({ trial }: { trial: TrialCardType }) {
  const { eligibility, locations } = trial;

  const ageRange = [
    eligibility.min_age_years != null ? `${eligibility.min_age_years}y` : null,
    eligibility.max_age_years != null ? `${eligibility.max_age_years}y` : null,
  ]
    .filter(Boolean)
    .join(" – ");

  return (
    <Card className="w-full">
      <CardHeader className="border-b pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <CardTitle className="text-sm font-semibold leading-snug line-clamp-2">
              {trial.brief_title}
            </CardTitle>
            <CardDescription className="mt-1 font-mono">{trial.nct_id}</CardDescription>
          </div>
          <StatusBadge status={trial.overall_status} />
        </div>

        <div className="flex flex-wrap gap-1 mt-2">
          {trial.phases.map((p) => (
            <PhaseBadge key={p} phase={p} />
          ))}
        </div>
      </CardHeader>

      <CardContent className="grid gap-3 pt-3 sm:grid-cols-2">
        <div className="space-y-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Sponsor</p>
          <p className="text-xs">{trial.lead_sponsor_name}</p>
          <p className="text-[10px] text-muted-foreground">{trial.lead_sponsor_class}</p>
        </div>

        <div className="space-y-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Eligibility</p>
          <p className="text-xs">
            {eligibility.sex}{ageRange ? `, ${ageRange}` : ""}
            {eligibility.accepts_healthy_volunteers ? " · Healthy volunteers OK" : ""}
          </p>
          {eligibility.short_summary && (
            <p className="text-[10px] text-muted-foreground line-clamp-2">{eligibility.short_summary}</p>
          )}
        </div>

        <div className="space-y-1">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Locations</p>
          <p className="text-xs">
            {locations.recruiting_sites} recruiting / {locations.total_sites} total sites
          </p>
          {locations.nearest_facility && (
            <p className="text-[10px] text-muted-foreground">
              Nearest: {locations.nearest_facility}
              {locations.nearest_distance_km != null
                ? ` (${locations.nearest_distance_km.toFixed(0)} km)`
                : ""}
            </p>
          )}
        </div>

        {trial.match_explanation && (
          <div className="space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Why matched</p>
            <p className="text-[10px] text-muted-foreground line-clamp-3">{trial.match_explanation}</p>
          </div>
        )}

        {trial.best_matching_chunk && (
          <div className="sm:col-span-2 space-y-1 rounded-md bg-muted/40 px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              Best match · {trial.best_matching_chunk.field_type}
            </p>
            <p className="text-[10px] text-foreground/80 line-clamp-3">
              {trial.best_matching_chunk.chunk_text}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

"use client";

import { useState, useTransition } from "react";
import { Plus, X, ChevronRight, Loader2 } from "lucide-react";
import type {
  MatchedTrial,
  MatchResult,
  CriterionVerdict,
  TrialSignal,
  Verdict,
} from "@repo/generated-schemas-web";
import {
  matchTrialsAction,
  matchTrialAction,
  screenPortfolioAction,
} from "@/lib/actions/eligibility-match/actions";
import {
  buildProfile,
  criterionCoverage,
  groupBySignal,
  isAssessable,
  unassessedTrials,
  type Pair,
} from "./match-logic";

// Keyed by the GraphQL enum's serialized values (UPPERCASE — GraphQL emits enum *names*,
// not the lowercase inference strings). Typed as Record<TrialSignal/Verdict, …> so the
// keys stay in lockstep with the generated schema and can't drift to the wrong casing.
const SIGNAL_META: Record<TrialSignal, { label: string; cls: string }> = {
  LIKELY_ELIGIBLE: { label: "Likely eligible", cls: "bg-green-100 text-green-800" },
  POSSIBLE: { label: "Possible", cls: "bg-amber-100 text-amber-800" },
  LIKELY_EXCLUDED: { label: "Likely excluded", cls: "bg-red-100 text-red-700" },
};

const VERDICT_META: Record<Verdict, { label: string; cls: string }> = {
  PASS: { label: "Pass", cls: "bg-green-100 text-green-800" },
  FAIL: { label: "Fail", cls: "bg-red-100 text-red-700" },
  UNCERTAIN: { label: "Uncertain", cls: "bg-amber-100 text-amber-800" },
  NOT_EVALUATED: { label: "Not eval.", cls: "bg-muted text-muted-foreground" },
};

/**
 * `mode` decides what the form screens against:
 *  - "search"    → all recruiting trials for a typed condition (patient-first search).
 *  - "portfolio" → only the site's open-trial portfolio, no condition (site-payer wedge).
 * Everything else — the profile form, ranked buckets, blockers, completeness, drill-in — is shared.
 */
export function MatchView({
  mode = "search",
  // Portfolio mode only: false disables "Screen patient" (an empty portfolio has nothing to
  // screen against). The parent keeps this in sync with the portfolio as trials are added.
  canScreen = true,
}: {
  mode?: "search" | "portfolio";
  canScreen?: boolean;
} = {}) {
  const isPortfolio = mode === "portfolio";
  // ── profile form state ──────────────────────────────────────────────────
  const [condition, setCondition] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("");
  const [ecog, setEcog] = useState("");
  const [stage, setStage] = useState("");
  const [treatmentNaive, setTreatmentNaive] = useState(false);
  const [biomarkers, setBiomarkers] = useState<Pair[]>([]);
  const [priorTherapies, setPriorTherapies] = useState<string[]>([]);
  const [washouts, setWashouts] = useState<Pair[]>([]);

  const [results, setResults] = useState<MatchedTrial[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Separate transitions: a drill-in must not disable the "Match trials" button, and vice versa.
  const [matchPending, startMatch] = useTransition();
  const [, startDrill] = useTransition();

  // Per-trial drill-in cache + which trial is expanded.
  const [verdicts, setVerdicts] = useState<Record<string, MatchResult | null>>({});
  const [openNct, setOpenNct] = useState<string | null>(null);
  // Profile snapshot taken at match time. Drill-ins reuse THIS, not the live form — otherwise
  // editing the form after ranking would make a trial's per-criterion verdicts disagree with
  // the bucket it was sorted into.
  const [matchedProfile, setMatchedProfile] =
    useState<ReturnType<typeof buildProfile> | null>(null);

  const currentProfile = () =>
    buildProfile({ age, sex, ecog, stage, treatmentNaive, biomarkers, priorTherapies, washouts });

  function onSubmit() {
    setError(null);
    setVerdicts({});
    setOpenNct(null);
    const profile = currentProfile();
    setMatchedProfile(profile);
    startMatch(async () => {
      const state = isPortfolio
        ? await screenPortfolioAction(profile)
        : await matchTrialsAction({ condition, profile });
      if (state?.error) {
        setError(state.error);
        setResults(null);
      } else {
        setResults(state?.results ?? []);
      }
    });
  }

  function toggleWhy(nctId: string) {
    if (openNct === nctId) {
      setOpenNct(null);
      return;
    }
    setOpenNct(nctId);
    if (verdicts[nctId] !== undefined) return; // cached
    const profile = matchedProfile ?? currentProfile();
    startDrill(async () => {
      const state = await matchTrialAction({ nctId, profile });
      setVerdicts((v) => ({ ...v, [nctId]: state?.error ? null : state?.result ?? null }));
    });
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-6">
      <div>
        <h2 className="text-lg font-semibold">
          {isPortfolio ? "Screen against your open trials" : "Find trials for your patient"}
        </h2>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {isPortfolio
            ? "Enter the patient's profile to see which of your portfolio trials they may be eligible for."
            : "Enter a condition and the patient's profile to rank recruiting trials by eligibility fit."}
        </p>
      </div>

      {/* ── Profile form ─────────────────────────────────────────────── */}
      <div className="flex flex-col gap-3 rounded-xl border bg-background p-4">
        {!isPortfolio && (
          <Field label="Condition">
            <input
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              placeholder="e.g. non-small cell lung cancer"
              className="w-full rounded-md border px-2.5 py-1.5 text-sm"
            />
          </Field>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Age">
            <input type="number" value={age} onChange={(e) => setAge(e.target.value)}
              className="w-full rounded-md border px-2.5 py-1.5 text-sm" />
          </Field>
          <Field label="Sex">
            <select value={sex} onChange={(e) => setSex(e.target.value)}
              className="w-full rounded-md border px-2.5 py-1.5 text-sm">
              <option value="">—</option>
              <option value="MALE">Male</option>
              <option value="FEMALE">Female</option>
            </select>
          </Field>
          <Field label="ECOG">
            <select value={ecog} onChange={(e) => setEcog(e.target.value)}
              className="w-full rounded-md border px-2.5 py-1.5 text-sm">
              <option value="">—</option>
              {[0, 1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </Field>
          <Field label="Stage">
            <input value={stage} onChange={(e) => setStage(e.target.value)} placeholder="IV"
              className="w-full rounded-md border px-2.5 py-1.5 text-sm" />
          </Field>
        </div>

        {/* Biomarkers (dynamic rows) */}
        <PairList
          label="Biomarkers"
          pairs={biomarkers}
          setPairs={setBiomarkers}
          keyPlaceholder="EGFR"
          valuePlaceholder="wild-type or 60"
        />

        {/* Prior therapies (dynamic text rows) */}
        <StringList
          label="Prior therapies"
          items={priorTherapies}
          setItems={setPriorTherapies}
          placeholder="e.g. checkpoint inhibitor"
        />

        {/* Washout timing — days since a therapy/event, for "within N days" criteria */}
        <PairList
          label="Days since last treatment"
          pairs={washouts}
          setPairs={setWashouts}
          keyPlaceholder="chemotherapy"
          valuePlaceholder="days, e.g. 14"
        />

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={treatmentNaive}
            onChange={(e) => setTreatmentNaive(e.target.checked)} />
          Treatment-naïve
        </label>

        <button
          onClick={onSubmit}
          disabled={
            matchPending ||
            (!isPortfolio && condition.trim().length < 2) ||
            (isPortfolio && !canScreen)
          }
          className="mt-1 inline-flex items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          {matchPending && <Loader2 className="h-4 w-4 animate-spin" />}
          {isPortfolio ? "Screen patient" : "Match trials"}
        </button>

        {isPortfolio && !canScreen && (
          <p className="text-[11px] text-muted-foreground">
            Add a trial under “Your open trials” above to screen against your portfolio.
          </p>
        )}
      </div>

      <p className="text-[11px] text-muted-foreground">
        Decision support only — not medical advice. Confirm eligibility with the trial site.
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* ── Ranked results ───────────────────────────────────────────── */}
      {results && results.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {isPortfolio
            ? "No portfolio trials to screen yet — add the trials your site is running under “Your open trials” above, then screen."
            : "No recruiting trials found for that condition."}
        </p>
      )}

      {results && results.length > 0 && (
        <div className="flex flex-col gap-4">
          {groupBySignal(results).map(({ signal, trials }) => {
            const meta = SIGNAL_META[signal];
            return (
              <div key={signal} className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${meta.cls}`}>
                    {meta.label}
                  </span>
                  <span className="text-xs text-muted-foreground">{trials.length}</span>
                </div>
                {trials.map((t) => (
                  <TrialRow
                    key={t.nct_id}
                    trial={t}
                    open={openNct === t.nct_id}
                    verdict={verdicts[t.nct_id]}
                    onToggle={() => toggleWhy(t.nct_id)}
                  />
                ))}
              </div>
            );
          })}

          {/* Trials that matched the condition but the matcher couldn't assess — kept apart
              from the ranked signal buckets so "no data" isn't mistaken for "borderline". */}
          {(() => {
            const unassessed = unassessedTrials(results);
            if (unassessed.length === 0) return null;
            return (
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                    Not enough data to assess
                  </span>
                  <span className="text-xs text-muted-foreground">{unassessed.length}</span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Recruiting trials matching the condition with no structured eligibility we can
                  check yet — review these manually.
                </p>
                {unassessed.map((t) => (
                  <TrialRow
                    key={t.nct_id}
                    trial={t}
                    open={openNct === t.nct_id}
                    verdict={verdicts[t.nct_id]}
                    onToggle={() => toggleWhy(t.nct_id)}
                  />
                ))}
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}

function PairList({
  label, pairs, setPairs, keyPlaceholder, valuePlaceholder,
}: {
  label: string; pairs: Pair[]; setPairs: (p: Pair[]) => void;
  keyPlaceholder: string; valuePlaceholder: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {pairs.map((p, i) => (
        <div key={i} className="flex gap-2">
          <input value={p.key} placeholder={keyPlaceholder}
            onChange={(e) => setPairs(pairs.map((x, j) => j === i ? { ...x, key: e.target.value } : x))}
            className="w-1/3 rounded-md border px-2.5 py-1.5 text-sm" />
          <input value={p.value} placeholder={valuePlaceholder}
            onChange={(e) => setPairs(pairs.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}
            className="flex-1 rounded-md border px-2.5 py-1.5 text-sm" />
          <button onClick={() => setPairs(pairs.filter((_, j) => j !== i))}
            className="rounded-md border px-2 text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button onClick={() => setPairs([...pairs, { key: "", value: "" }])}
        className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <Plus className="h-3.5 w-3.5" /> Add {label.toLowerCase()}
      </button>
    </div>
  );
}

function StringList({
  label, items, setItems, placeholder,
}: {
  label: string; items: string[]; setItems: (s: string[]) => void; placeholder: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {items.map((v, i) => (
        <div key={i} className="flex gap-2">
          <input value={v} placeholder={placeholder}
            onChange={(e) => setItems(items.map((x, j) => j === i ? e.target.value : x))}
            className="flex-1 rounded-md border px-2.5 py-1.5 text-sm" />
          <button onClick={() => setItems(items.filter((_, j) => j !== i))}
            className="rounded-md border px-2 text-muted-foreground hover:text-foreground">
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ))}
      <button onClick={() => setItems([...items, ""])}
        className="inline-flex w-fit items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
        <Plus className="h-3.5 w-3.5" /> Add {label.toLowerCase()}
      </button>
    </div>
  );
}

function TrialRow({
  trial, open, verdict, onToggle,
}: {
  trial: MatchedTrial; open: boolean; verdict: MatchResult | null | undefined;
  onToggle: () => void;
}) {
  const cov = criterionCoverage(trial);
  return (
    <div className="rounded-lg border bg-background">
      <button onClick={onToggle} className="flex w-full items-start gap-3 p-3 text-left">
        <ChevronRight className={`mt-0.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`} />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{trial.brief_title ?? trial.nct_id}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {trial.nct_id} · {trial.overall_status ?? "—"}
            {trial.phases.length > 0 && ` · ${trial.phases.join(", ")}`}
          </p>
          {/* Inline "why excluded" — the failing criterion, no drill-in needed. */}
          {trial.blockers.length > 0 && (
            <p className="mt-0.5 text-[11px] text-red-700">
              Blocked: {trial.blockers[0].reason}
              {trial.blockers.length > 1 && ` · +${trial.blockers.length - 1} more`}
            </p>
          )}
        </div>
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {isAssessable(trial) ? (
            <>
              {trial.n_pass}✓ {trial.n_fail}✗ {trial.n_uncertain}?
              {cov.total > cov.checked && ` · ${cov.checked}/${cov.total} checked`}
            </>
          ) : trial.has_criteria ? (
            `${trial.n_not_evaluated} criteria · manual review`
          ) : (
            "no eligibility data"
          )}
        </span>
      </button>

      {open && (
        <div className="border-t px-3 py-2">
          {verdict === undefined ? (
            <p className="text-xs text-muted-foreground">Loading…</p>
          ) : verdict === null || !trial.has_criteria ? (
            <p className="text-xs text-muted-foreground">
              No structured eligibility extracted for this trial yet.
            </p>
          ) : (
            <>
              <p className="mb-1.5 text-[11px] text-muted-foreground">
                Machine-checked {cov.checked} of {cov.total} criteria
                {cov.total > cov.checked &&
                  ` · ${cov.total - cov.checked} need manual review`}
              </p>
              <ul className="flex flex-col gap-1.5">
                {verdict.verdicts.map((v: CriterionVerdict, i: number) => {
                  const meta = VERDICT_META[v.verdict];
                  return (
                    <li key={i} className="flex gap-2 text-xs">
                      <span
                        className={`mt-0.5 shrink-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[10px] font-medium ${meta?.cls ?? ""}`}
                      >
                        {meta?.label ?? v.verdict}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span>{v.text}</span>
                        <span className="block text-[11px] text-muted-foreground">{v.reason}</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}

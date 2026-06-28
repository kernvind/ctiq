import type { MatchedTrial, MatchResult } from "@repo/generated-schemas-web";

/** Patient-first: ranked candidate trials for a profile + condition. */
export type MatchTrialsState =
  | { error?: undefined; results: MatchedTrial[] }
  | { error: string; results?: undefined }
  | null;

/** Per-trial drill-in: full verdicts for one trial (null = no extracted criteria yet). */
export type MatchTrialState =
  | { error?: undefined; result: MatchResult | null }
  | { error: string; result?: undefined }
  | null;

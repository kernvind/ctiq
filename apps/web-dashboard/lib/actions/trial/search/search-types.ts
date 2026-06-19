import type { TrialCard } from "@repo/generated-schemas-web";

/** Shared result shape for the trial-search server actions (public + authed). */
export type SearchState = {
  error?: string;
  results?: TrialCard[];
  query?: string;
} | null;

"use server";

import {
  ZodMatchTrialsSchema,
  ZodMatchTrialSchema,
} from "@repo/zod-validations";
import { withAuthedSdk } from "@/lib/authed-sdk";
import { flattenZodErrors } from "@/lib/zod-errors";
import { logger } from "@/lib/logger";
import type { MatchTrialsState, MatchTrialState } from "./match-types";

/**
 * Eligibility-match server actions (ROADMAP step 6). Clinician-only — the api-core
 * resolver is gated to the CLINICIAN role, and these use the authed sdk. The patient
 * profile is forwarded for evaluation and never persisted (PHI gate).
 */

function messageOf(err: unknown): string {
  return (
    (err as { response?: { errors?: { message: string }[] } })?.response
      ?.errors?.[0]?.message ?? "Something went wrong. Please try again."
  );
}

/** Patient-first: rank recruiting trials for a condition by the profile's eligibility fit. */
export async function matchTrialsAction(
  input: unknown,
): Promise<MatchTrialsState> {
  const parsed = ZodMatchTrialsSchema.safeParse(input);
  if (!parsed.success) {
    return { error: flattenZodErrors(parsed.error) };
  }
  try {
    const { condition, profile, topK, recruitingOnly } = parsed.data;
    const data = await withAuthedSdk((sdk) =>
      sdk.matchTrials_mutation({ condition, profile, topK, recruitingOnly }),
    );
    // Safe metadata only — never the profile (PHI) or the result bodies.
    logger.info({ resultCount: data.matchTrials.length }, "matchTrials completed");
    return { results: data.matchTrials };
  } catch (err) {
    return { error: messageOf(err) };
  }
}

/** Per-trial drill-in: per-criterion verdicts for one trial. */
export async function matchTrialAction(
  input: unknown,
): Promise<MatchTrialState> {
  const parsed = ZodMatchTrialSchema.safeParse(input);
  if (!parsed.success) {
    return { error: flattenZodErrors(parsed.error) };
  }
  try {
    const { nctId, profile } = parsed.data;
    const data = await withAuthedSdk((sdk) =>
      sdk.matchTrial_mutation({ nctId, profile }),
    );
    // Safe metadata only — log the trial id and whether criteria existed, never the
    // profile (PHI) or the per-criterion verdicts.
    logger.info(
      { nctId, matched: data.matchTrial != null },
      "matchTrial completed",
    );
    return { result: data.matchTrial ?? null };
  } catch (err) {
    return { error: messageOf(err) };
  }
}

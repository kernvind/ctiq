/**
 * Recruitment-status classification for trial results.
 *
 * The patient mental model is "can I join this trial right now?" — so we split results
 * into trials *open for enrollment* vs. everything else (completed, terminated, etc.).
 * Surfacing a closed trial as if it were actionable is misleading, so the classifier
 * fails safe: anything unknown/missing is treated as NOT open.
 *
 * Pure module (no React) so it can be unit-tested and used from either a Server or
 * Client Component.
 */

// ClinicalTrials.gov overallStatus values that mean a patient could still enrol.
// ACTIVE_NOT_RECRUITING is intentionally excluded — the study is ongoing but not taking
// new participants, which is not actionable for someone trying to join.
const OPEN_ENROLLMENT_STATUSES = new Set([
  "RECRUITING",
  "NOT_YET_RECRUITING",
  "ENROLLING_BY_INVITATION",
  "AVAILABLE",
]);

/** Normalize a status to the CT.gov enum form: upper-case, non-alphanumerics → `_`. */
function normalizeStatus(status: string): string {
  return status.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_");
}

/** True only for statuses where a patient may still be able to enrol. */
export function isOpenForEnrollment(status?: string | null): boolean {
  if (!status) return false;
  return OPEN_ENROLLMENT_STATUSES.has(normalizeStatus(status));
}

/**
 * Split trials into `open` (still enrolling) and `closed` (everything else), preserving
 * the original order within each group. Generic over anything carrying `overall_status`.
 */
export function partitionByEnrollment<T extends { overall_status?: string | null }>(
  trials: T[],
): { open: T[]; closed: T[] } {
  const open: T[] = [];
  const closed: T[] = [];
  for (const trial of trials) {
    (isOpenForEnrollment(trial.overall_status) ? open : closed).push(trial);
  }
  return { open, closed };
}

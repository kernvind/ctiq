import { ZodNctIdSchema } from "@repo/zod-validations";

/**
 * Parsing for the side-by-side comparison route (`/compare?ids=NCT...,NCT...`).
 *
 * Comparison is only meaningful for a small number of trials, so the id list is
 * validated (real NCT ids only), de-duplicated, upper-cased, and capped. Kept as a pure
 * module so the URL contract is unit-tested independently of the page.
 */

export const MIN_COMPARE = 2;
export const MAX_COMPARE = 3;

/** Validate, normalize, de-dupe and cap the `ids` query param into NCT ids. */
export function parseCompareIds(raw: string | string[] | undefined): string[] {
  const text = Array.isArray(raw) ? raw.join(",") : (raw ?? "");
  const seen = new Set<string>();
  const ids: string[] = [];

  for (const part of text.split(",")) {
    const parsed = ZodNctIdSchema.safeParse(part);
    if (!parsed.success) continue;
    const id = parsed.data.toUpperCase();
    if (seen.has(id)) continue;
    seen.add(id);
    ids.push(id);
    if (ids.length >= MAX_COMPARE) break;
  }

  return ids;
}

/** Build the `/compare` href from a set of selected ids (inverse of parseCompareIds). */
export function buildCompareHref(ids: string[]): string {
  return `/compare?ids=${parseCompareIds(ids).join(",")}`;
}

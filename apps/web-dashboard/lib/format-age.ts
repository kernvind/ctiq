/**
 * Eligibility age formatting.
 *
 * `min_age_years` / `max_age_years` are floats the ETL parses from CT.gov strings like
 * "1 Month" or "5 Days" — so a 1-month minimum arrives as 0.0833…. Printing the raw float
 * (`0.08333333333333333y`) is the bug this fixes: sub-year ages render as months or days,
 * and floating-point noise is rounded away.
 *
 * Pure module so it's unit-tested once and shared by the card, detail, and compare views.
 */

const MONTHS_PER_YEAR = 12;
const DAYS_PER_YEAR = 365;

/**
 * Format an age given in (fractional) years into a compact label: years for >= 1 (and for
 * exactly 0 = newborn), months for >= ~1 month, days below that. Returns null for no value.
 * Years are rounded to at most one decimal so float noise (17.999…) prints cleanly.
 */
export function formatAgeYears(years?: number | null): string | null {
  if (years == null) return null;

  if (years >= 1 || years === 0) {
    return `${Math.round(years * 10) / 10}y`;
  }
  if (years >= 1 / MONTHS_PER_YEAR) {
    return `${Math.round(years * MONTHS_PER_YEAR)}mo`;
  }
  return `${Math.round(years * DAYS_PER_YEAR)}d`;
}

/**
 * Format a single age bound, preferring the exact CT.gov raw string ("18 Years",
 * "1 Month") when present and falling back to the parsed-float formatter otherwise.
 */
export function formatAgeBound(
  raw?: string | null,
  years?: number | null,
): string | null {
  const trimmed = raw?.trim();
  if (trimmed) return trimmed;
  return formatAgeYears(years);
}

/** Format an eligibility age range; shows whichever bound(s) exist, "" if none. */
export function formatAgeRange(
  min: { raw?: string | null; years?: number | null },
  max: { raw?: string | null; years?: number | null },
): string {
  return [
    formatAgeBound(min.raw, min.years),
    formatAgeBound(max.raw, max.years),
  ]
    .filter((v): v is string => v !== null)
    .join(" – ");
}

/**
 * Study-rigor descriptors: turn the trial design enums (allocation, masking,
 * intervention model) into compact human labels a clinician can scan — e.g.
 * "Randomized · Double-blind · Parallel" — without reading the detailed description.
 *
 * Pure module (no React) so it's unit-tested and reusable from the detail view and the
 * side-by-side comparison view. Values come from ClinicalTrials.gov `designInfo`.
 */

interface DesignFields {
  allocation?: string | null;
  masking?: string | null;
  intervention_model?: string | null;
}

const ALLOCATION_LABELS: Record<string, string> = {
  RANDOMIZED: "Randomized",
  NON_RANDOMIZED: "Non-randomized",
};

const MASKING_LABELS: Record<string, string> = {
  NONE: "Open-label",
  SINGLE: "Single-blind",
  DOUBLE: "Double-blind",
  TRIPLE: "Triple-blind",
  QUADRUPLE: "Quadruple-blind",
};

const MODEL_LABELS: Record<string, string> = {
  SINGLE_GROUP: "Single-group",
  PARALLEL: "Parallel",
  CROSSOVER: "Crossover",
  FACTORIAL: "Factorial",
  SEQUENTIAL: "Sequential",
};

function normalize(value: string): string {
  return value.trim().toUpperCase().replace(/[^A-Z0-9]+/g, "_");
}

// Title-case an unrecognized enum so a new CT.gov value still renders readably instead
// of being silently dropped (e.g. "SOME_NEW_MODEL" -> "Some new model").
function titleCase(value: string): string {
  const lower = normalize(value).replace(/_/g, " ").toLowerCase().trim();
  return lower ? lower.charAt(0).toUpperCase() + lower.slice(1) : "";
}

function describe(
  value: string | null | undefined,
  labels: Record<string, string>,
  { dropValues = [] as string[] } = {},
): string | null {
  if (!value) return null;
  const key = normalize(value);
  if (dropValues.includes(key)) return null;
  return labels[key] ?? titleCase(value);
}

/**
 * Compact rigor labels in reading order [allocation, masking, model]. Missing fields and
 * non-informative values (allocation "NA") are omitted; unrecognized values fall back to
 * a title-cased form. Returns `[]` when no design info is present.
 */
export function rigorBadges(design: DesignFields): string[] {
  return [
    describe(design.allocation, ALLOCATION_LABELS, { dropValues: ["NA", "N_A"] }),
    describe(design.masking, MASKING_LABELS),
    describe(design.intervention_model, MODEL_LABELS, { dropValues: ["NA", "N_A"] }),
  ].filter((label): label is string => label !== null);
}

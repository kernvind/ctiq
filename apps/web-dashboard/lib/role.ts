/**
 * Display helpers for the user's role (PATIENT / CLINICIAN / ANALYST / ADMIN). Pure
 * module so role-aware UI labels are tested once and shared across components.
 */

const ROLE_LABELS: Record<string, string> = {
  PATIENT: "Patient",
  CLINICIAN: "Clinician",
  ANALYST: "Analyst",
  ADMIN: "Admin",
};

/** Human label for a role; falls back to the raw value, "" for none. */
export function roleLabel(role?: string | null): string {
  if (!role) return "";
  return ROLE_LABELS[role.toUpperCase()] ?? role;
}

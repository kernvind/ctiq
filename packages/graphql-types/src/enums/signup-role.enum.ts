import { registerEnumType } from '@nestjs/graphql';

/**
 * Roles a user may self-select at signup.
 *
 * ADMIN (and any future privileged role) is intentionally excluded — roles are never
 * self-assignable to a privileged level. Self-selected CLINICIAN / ANALYST are treated
 * as unverified until a verification step exists; today role only drives UX, so this is
 * acceptable, but it must be gated before any role unlocks privileges or PHI.
 *
 * Values mirror a subset of the `Role` enum in @repo/db. They are duplicated here (not
 * imported) on purpose: this contract package is consumed by the frontend and must not
 * pull in the Prisma client. The api-core boundary maps SignupRole -> Role with a
 * compile-time-checked table so the two cannot silently drift.
 */
export enum SignupRole {
  PATIENT = 'PATIENT',
  CLINICIAN = 'CLINICIAN',
  ANALYST = 'ANALYST',
}

registerEnumType(SignupRole, {
  name: 'SignupRole',
  description: 'Roles a user may choose at signup (excludes ADMIN).',
});

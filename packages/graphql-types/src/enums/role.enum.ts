import { registerEnumType } from '@nestjs/graphql';

/**
 * A user's full assigned role. Mirrors the `Role` enum in @repo/db (duplicated, not
 * imported, because this contract package is consumed by the frontend and must not pull
 * in the Prisma client). Unlike SignupRole this includes ADMIN — `me` must be able to
 * report an admin's role, even though ADMIN can never be self-assigned at signup.
 */
export enum UserRole {
  PATIENT = 'PATIENT',
  CLINICIAN = 'CLINICIAN',
  ANALYST = 'ANALYST',
  ADMIN = 'ADMIN',
}

registerEnumType(UserRole, {
  name: 'Role',
  description: "A user's assigned role.",
});

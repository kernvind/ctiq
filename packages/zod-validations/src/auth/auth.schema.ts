import { z } from "zod";
const PASSWORD_ERROR_MESSAGE =
  "Password must be at least 8 characters long and at most 50 characters long";
const EMAIL_ERROR_MESSAGE = "Must be a valid email address";

const PASSWORD_VALIDATION_ZOD_SIGNUP = z
  .string()
  .min(8, PASSWORD_ERROR_MESSAGE)
  .max(50, PASSWORD_ERROR_MESSAGE);

const PASSWORD_VALIDATION_ZOD_SIGNIN = z
  .string()
  .min(8, "Invalid password")
  .max(50, "Invalid password");

export const ZodLoginSchema = z.object({
  email: z.email(EMAIL_ERROR_MESSAGE),
  password: PASSWORD_VALIDATION_ZOD_SIGNIN,
});

// Roles a user may self-select at signup. Mirrors the SignupRole enum in
// @repo/graphql-types and a subset of @repo/db's Role — ADMIN is excluded so it can
// never be self-assigned. Kept as a literal list here because this package is consumed
// by the frontend and must not depend on the ORM.
export const SIGNUP_ROLES = ["PATIENT", "CLINICIAN", "ANALYST"] as const;

export const ZodSignupSchema = z.object({
  email: z.email(EMAIL_ERROR_MESSAGE),
  name: z.string().min(1).max(100).optional(),
  password: PASSWORD_VALIDATION_ZOD_SIGNUP,
  role: z.enum(SIGNUP_ROLES).default("PATIENT"),
});
// extended schema — used by Next.js forms only
export const ZodRegisterFormSchema = ZodSignupSchema.extend({
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
});

export type ZodLoginInput = z.infer<typeof ZodLoginSchema>;
export type ZodSignupInput = z.infer<typeof ZodSignupSchema>;

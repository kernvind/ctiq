import { z } from "zod";

export const ZodLoginSchema = z.object({
  username: z.string().min(3).max(50),
  password: z.string().min(8).max(50),
});

// Roles a user may self-select at signup. Mirrors the SignupRole enum in
// @repo/graphql-types and a subset of @repo/db's Role — ADMIN is excluded so it can
// never be self-assigned. Kept as a literal list here because this package is consumed
// by the frontend and must not depend on the ORM.
export const SIGNUP_ROLES = ["PATIENT", "CLINICIAN", "ANALYST"] as const;

export const ZodSignupSchema = z.object({
  email: z.email(),
  username: z.string().min(3).max(50),
  name: z.string().min(1).max(100).optional(),
  password: z.string().min(8).max(50),
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

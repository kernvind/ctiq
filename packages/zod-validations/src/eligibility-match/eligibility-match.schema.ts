import { z } from "zod";
import { ZodNctIdSchema } from "../trial-search/trial-search.schema";

/**
 * Validation for the eligibility matcher (ROADMAP step 6). Shared by the web form and the
 * api-core resolver. Mirrors the GraphQL PatientProfileInput + match args. The profile is
 * never persisted (PHI gate) — this only validates shape before it's forwarded.
 */

export const ZodBiomarkerSchema = z.object({
  marker: z.string().trim().min(1, "Marker is required"),
  // Free text: numeric ("60") or status ("wild-type"); the service decides.
  value: z.string().trim().min(1, "Value is required"),
});
export type ZodBiomarkerInput = z.infer<typeof ZodBiomarkerSchema>;

export const ZodLabSchema = z.object({
  analyte: z.string().trim().min(1, "Analyte is required"),
  value: z.number(),
});
export type ZodLabInput = z.infer<typeof ZodLabSchema>;

export const ZodPatientProfileSchema = z.object({
  age_years: z.number().min(0).max(120).nullish(),
  sex: z.enum(["MALE", "FEMALE"]).nullish(),
  ecog: z.number().int().min(0).max(4).nullish(),
  stage: z.string().trim().max(20).nullish(),
  biomarkers: z.array(ZodBiomarkerSchema).default([]),
  prior_therapies: z.array(z.string().trim().min(1)).default([]),
  treatment_naive: z.boolean().nullish(),
  labs: z.array(ZodLabSchema).default([]),
});
export type ZodPatientProfileInput = z.infer<typeof ZodPatientProfileSchema>;

// Standalone condition schema — used per-arg by the api-core resolver (zodPipe).
export const ZodConditionSchema = z.string().trim().min(2).max(200);
export type ZodConditionInput = z.infer<typeof ZodConditionSchema>;

// Patient-first: find & rank trials for a condition by the patient's eligibility fit.
export const ZodMatchTrialsSchema = z.object({
  condition: ZodConditionSchema,
  profile: ZodPatientProfileSchema,
  topK: z.number().int().min(1).max(200).default(50),
  recruitingOnly: z.boolean().default(true),
});
export type ZodMatchTrialsInput = z.infer<typeof ZodMatchTrialsSchema>;

// Per-trial drill-in: evaluate one trial against the profile.
export const ZodMatchTrialSchema = z.object({
  nctId: ZodNctIdSchema,
  profile: ZodPatientProfileSchema,
});
export type ZodMatchTrialInput = z.infer<typeof ZodMatchTrialSchema>;

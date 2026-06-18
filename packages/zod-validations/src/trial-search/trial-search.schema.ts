import { z } from "zod";
export const ZodTrialSearchSchema = z.object({
  q: z.string().min(10).max(500),
});

export type ZodTrialSearchInput = z.infer<typeof ZodTrialSearchSchema>;

// ClinicalTrials.gov NCT id, e.g. NCT01234567 (case-insensitive on input).
export const ZodNctIdSchema = z
  .string()
  .trim()
  .regex(/^NCT\d{8}$/i, "Must be a valid NCT id, e.g. NCT01234567");

export type ZodNctIdInput = z.infer<typeof ZodNctIdSchema>;

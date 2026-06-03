import { z } from "zod";
export const ZodTrialSearchSchema = z.object({
  q: z.string().min(10).max(500),
});

export type ZodTrialSearchInput = z.infer<typeof ZodTrialSearchSchema>;

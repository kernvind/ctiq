import { z } from "zod";

// A saved landscape: a named, re-runnable query the analyst monitors. v1 wraps the
// existing semantic search (q + optional phase) — the same `q` bounds as ZodTrialSearchSchema
// so a landscape always runs a valid search. The shape is intentionally small now; the
// future NL-to-query agent will extend the stored spec, not replace this contract.
export const ZodCreateLandscapeSchema = z.object({
  name: z.string().min(1).max(100),
  q: z.string().min(10).max(500),
  phase: z.string().max(40).optional(),
});

export type ZodCreateLandscapeInput = z.infer<typeof ZodCreateLandscapeSchema>;

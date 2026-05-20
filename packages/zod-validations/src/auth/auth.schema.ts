import { z } from "zod";

export const ZodLoginSchema = z.object({
  username: z.string().min(3).max(50),
  password: z.string().min(8).max(50),
});

export const ZodSignupSchema = z.object({
  email: z.email(),
  username: z.string().min(3).max(50),
  name: z.string().min(1).max(100).optional(),
  password: z.string().min(8).max(50),
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

import { z } from 'zod';

export const LoginSchema = z.object({
  username: z.string(),
  password: z.string().min(1),
});

export type LoginDto = z.infer<typeof LoginSchema>;

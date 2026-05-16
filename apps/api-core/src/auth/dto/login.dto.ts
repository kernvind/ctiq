import { z } from 'zod';
import { UserInputSchema } from '@repo/db';

export const LoginSchema = UserInputSchema.pick({ username: true }).extend({
  password: z.string().min(1),
});

export type LoginDto = z.infer<typeof LoginSchema>;

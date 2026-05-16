import { z } from 'zod';
import { UserCreateInputObjectZodSchema } from '@repo/db';

export const SignupSchema = UserCreateInputObjectZodSchema.pick({
  email: true,
  username: true,
  name: true,
}).extend({
  password: z.string().min(8),
});

export type SignupDto = z.infer<typeof SignupSchema>;

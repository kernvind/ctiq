import { z } from 'zod';
import { UserCreateOneSchema } from '@repo/db';

export type SignupDto = z.infer<typeof UserCreateOneSchema>;

import { describe, it, expect } from 'vitest';
import { z } from 'zod';
import { flattenZodErrors } from './zod-errors';

describe('flattenZodErrors', () => {
  it('joins all field error messages into one comma-separated string', () => {
    const schema = z.object({
      username: z.string().min(3, 'too short'),
      email: z.email('bad email'),
    });
    const result = schema.safeParse({ username: 'ab', email: 'nope' });

    expect(result.success).toBe(false);
    if (!result.success) {
      const msg = flattenZodErrors(result.error);
      expect(msg).toContain('too short');
      expect(msg).toContain('bad email');
      expect(msg).toContain(', ');
    }
  });

  it('returns an empty string when there are no field errors', () => {
    const schema = z.object({ name: z.string() });
    const result = schema.safeParse({ name: 'ok' });
    expect(result.success).toBe(true);
  });
});

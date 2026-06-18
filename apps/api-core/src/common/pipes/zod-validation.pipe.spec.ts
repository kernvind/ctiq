import { BadRequestException } from '@nestjs/common';
import { z } from 'zod';
import { ZodValidationPipe, zodPipe } from './zod-validation.pipe';

const schema = z.object({
  username: z.string().min(3),
  age: z.number().int(),
});

describe('ZodValidationPipe', () => {
  it('returns the parsed data for valid input', () => {
    const pipe = new ZodValidationPipe(schema);
    expect(pipe.transform({ username: 'abc', age: 5 })).toEqual({
      username: 'abc',
      age: 5,
    });
  });

  it('throws BadRequestException with flattened per-field errors for invalid input', () => {
    const pipe = zodPipe(schema);

    let thrown: unknown;
    try {
      pipe.transform({ username: 'ab', age: 'not-a-number' });
    } catch (e) {
      thrown = e;
    }

    expect(thrown).toBeInstanceOf(BadRequestException);
    const response = (thrown as BadRequestException).getResponse() as {
      message: string;
      errors: Record<string, string[]>;
    };
    expect(response.message).toBe('Validation failed');
    // both invalid fields are reported, keyed by field name
    expect(response.errors.username?.length).toBeGreaterThan(0);
    expect(response.errors.age?.length).toBeGreaterThan(0);
  });

  it('does not let unknown keys through (returns only the schema shape)', () => {
    const pipe = zodPipe(schema);
    const out = pipe.transform({ username: 'abc', age: 5, extra: 'x' }) as Record<
      string,
      unknown
    >;
    expect(out).not.toHaveProperty('extra');
  });
});

import { BadRequestException, PipeTransform } from '@nestjs/common';
import { ZodSchema } from 'zod';

export class ZodValidationPipe implements PipeTransform {
  constructor(private schema: ZodSchema) {}

  transform(value: unknown) {
    const result = this.schema.safeParse(value);

    if (!result.success) {
      throw new BadRequestException({
        message: 'Validation failed',
        errors: result.error.flatten((issue) => issue.message).fieldErrors,
      });
    }

    return result.data;
  }
}
// factory — cleaner at call site
export const zodPipe = (schema: ZodSchema) => new ZodValidationPipe(schema);

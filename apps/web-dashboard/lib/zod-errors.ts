import { ZodError } from "zod";

export function flattenZodErrors(error: ZodError): string {
  const fieldErrors = error.flatten((issue) => issue.message).fieldErrors;
  return Object.values(fieldErrors).flat().join(", ");
}

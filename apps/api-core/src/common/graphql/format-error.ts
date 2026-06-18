import { GraphQLFormattedError } from 'graphql';

const INTERNAL_CODE = 'INTERNAL_SERVER_ERROR';
const INTERNAL_MESSAGE = 'Internal server error';

/**
 * Sanitizes every GraphQL error before it leaves api-core, so nothing raw ever reaches
 * the client (browser). This is the second line of defense alongside
 * GlobalExceptionFilter: it also catches errors produced by Apollo's own
 * validation/execution layer (e.g. a non-nullable field returning null when the
 * inference-service response shape doesn't match the GraphQL type) which never pass
 * through the resolver/filter.
 *
 * - Always removes stack traces (Apollo includes them when NODE_ENV !== 'production').
 * - Masks the message for internal / 5xx errors so internals don't leak.
 * - Preserves safe client-facing messages for 4xx (validation, auth, conflicts).
 */
export function formatGraphQLError(
  error: GraphQLFormattedError,
): GraphQLFormattedError {
  const extensions: Record<string, unknown> = { ...(error.extensions ?? {}) };

  // Stack traces must never reach the client.
  delete extensions.stacktrace;

  const code =
    typeof extensions.code === 'string' ? extensions.code : INTERNAL_CODE;
  const statusCode =
    typeof extensions.statusCode === 'number'
      ? extensions.statusCode
      : undefined;

  const isInternal =
    code === INTERNAL_CODE || (statusCode !== undefined && statusCode >= 500);

  return {
    message: isInternal ? INTERNAL_MESSAGE : error.message,
    path: error.path,
    extensions: {
      code,
      ...(statusCode !== undefined ? { statusCode } : {}),
    },
  };
}

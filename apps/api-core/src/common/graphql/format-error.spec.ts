import { GraphQLFormattedError } from 'graphql';
import { formatGraphQLError } from './format-error';

const err = (over: Partial<GraphQLFormattedError>): GraphQLFormattedError => ({
  message: 'original message',
  ...over,
});

describe('formatGraphQLError', () => {
  it('strips stack traces from every error', () => {
    const out = formatGraphQLError(
      err({
        message: 'bad input',
        extensions: {
          code: 'BadRequestException',
          statusCode: 400,
          stacktrace: ['Error: bad input', '  at resolver (...)'],
        },
      }),
    );
    expect(out.extensions).not.toHaveProperty('stacktrace');
  });

  it('preserves safe client messages for 4xx errors', () => {
    const out = formatGraphQLError(
      err({
        message: 'Invalid credentials',
        extensions: { code: 'UnauthorizedException', statusCode: 401 },
      }),
    );
    expect(out.message).toBe('Invalid credentials');
    expect(out.extensions).toMatchObject({ code: 'UnauthorizedException', statusCode: 401 });
  });

  it('masks the message for 5xx errors', () => {
    const out = formatGraphQLError(
      err({
        message: 'connect ECONNREFUSED 10.0.0.5:5432',
        extensions: { code: 'DATABASE_ERROR', statusCode: 500 },
      }),
    );
    expect(out.message).toBe('Internal server error');
    expect(out.message).not.toContain('ECONNREFUSED');
  });

  it('masks a schema-mismatch / non-nullable-field error (no safe code)', () => {
    // This is the trial-search case: inference-service returns a shape that does not
    // satisfy the TrialCard type, so Apollo raises this with stacktrace and no code.
    const out = formatGraphQLError(
      err({
        message:
          'Cannot return null for non-nullable field TrialCard.brief_title.',
        extensions: { stacktrace: ['GraphQLError: Cannot return null ...'] },
      }),
    );
    expect(out.message).toBe('Internal server error');
    expect(out.extensions?.code).toBe('INTERNAL_SERVER_ERROR');
    expect(out.extensions).not.toHaveProperty('stacktrace');
    // The raw field/type detail must not leak.
    expect(out.message).not.toContain('TrialCard');
  });

  it('keeps client query-validation messages (helpful, not internal) but no stacktrace', () => {
    const out = formatGraphQLError(
      err({
        message: 'Cannot query field "foo" on type "Query".',
        extensions: {
          code: 'GRAPHQL_VALIDATION_FAILED',
          stacktrace: ['...'],
        },
      }),
    );
    expect(out.message).toContain('Cannot query field');
    expect(out.extensions).not.toHaveProperty('stacktrace');
  });
});

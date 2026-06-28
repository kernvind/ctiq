/**
 * Auth GraphQL end-to-end check, run as a plain Node process (via ts-node) rather than
 * inside a Vitest/Jest worker — booting the full Nest app + Apollo + Prisma + Fastify +
 * native bcrypt inside a forked test worker segfaults on the Linux CI runner.
 *
 * Boots the real AppModule against an ephemeral Postgres (Testcontainers) and drives the
 * GraphQL auth flow. Exits non-zero if any assertion fails. Requires Docker.
 *
 * Run: pnpm --filter api-core test:e2e
 */
import 'reflect-metadata';
import * as assert from 'node:assert/strict';
import * as path from 'node:path';
import { execSync } from 'node:child_process';
import { writeSync } from 'node:fs';
import { NestFactory } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { PostgreSqlContainer } from '@testcontainers/postgresql';
import { AppModule } from '../src/app.module';

interface GqlResponse {
  data?: Record<string, any>;
  errors?: Array<{ message: string; extensions?: Record<string, unknown> }>;
}

const SIGNUP =
  'mutation($i:SignupInput!){signup(input:$i){accessToken refreshToken}}';
const LOGIN =
  'mutation($i:LoginInput!){login(input:$i){accessToken refreshToken}}';
const REFRESH =
  'mutation($rt:String!){refresh(refreshToken:$rt){accessToken refreshToken}}';
const LOGOUT = 'mutation($rt:String!){logout(refreshToken:$rt)}';
const MATCH_TRIALS =
  'mutation($c:String!,$p:PatientProfileInput!){matchTrials(condition:$c,profile:$p){nct_id signal}}';

async function main(): Promise<void> {
  const container = await new PostgreSqlContainer('postgres:16-alpine').start();
  const url = container.getConnectionUri();

  const dbDir = path.resolve(__dirname, '../../../packages/db');
  execSync('npx prisma db push --accept-data-loss', {
    cwd: dbDir,
    env: { ...process.env, DATABASE_URL: url },
    stdio: 'inherit',
  });

  process.env.DATABASE_URL = url;
  process.env.JWT_SECRET = 'test-secret';
  process.env.JWT_EXPIRES_IN = '15m';
  process.env.REFRESH_TOKEN_TTL_DAYS = '30';
  process.env.NODE_ENV = 'production';
  // TrialSearchModule's HttpModule resolves these at boot via getOrThrow. The auth flow
  // never calls trial-search, so dummy values are enough to let the app start.
  process.env.SEARCH_API_URL = 'http://localhost:9999';
  process.env.SEARCH_API_TOKEN = 'test-token';

  // abortOnError:false -> a bootstrap error is THROWN (so we can report it) instead of
  // Nest logging it and calling process.exit(1) silently. Logger stays on so Nest also
  // prints what failed (NODE_ENV=production -> JSON, no pino-pretty transport worker).
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    new FastifyAdapter(),
    { abortOnError: false },
  );
  await app.init();
  await app.getHttpAdapter().getInstance().ready();

  const gql = async (
    query: string,
    variables: Record<string, unknown> = {},
  ): Promise<GqlResponse> => {
    const res = await app.inject({
      method: 'POST',
      url: '/graphql',
      headers: { 'content-type': 'application/json' },
      payload: JSON.stringify({ query, variables }),
    });
    return res.json() as GqlResponse;
  };

  const gqlAuth = async (
    query: string,
    variables: Record<string, unknown>,
    token: string,
  ): Promise<GqlResponse> => {
    const res = await app.inject({
      method: 'POST',
      url: '/graphql',
      headers: {
        'content-type': 'application/json',
        authorization: `Bearer ${token}`,
      },
      payload: JSON.stringify({ query, variables }),
    });
    return res.json() as GqlResponse;
  };

  const signupToken = async (
    email: string,
    role: string,
  ): Promise<string> => {
    const s = await gql(SIGNUP, { i: { email, password: 'password123', role } });
    assert.equal(s.errors, undefined, `signup ${role} failed`);
    return s.data?.signup.accessToken as string;
  };

  let failures = 0;
  const test = async (name: string, fn: () => Promise<void>) => {
    try {
      await fn();
      console.log(`  ✓ ${name}`);
    } catch (err) {
      failures += 1;
      console.error(`  ✗ ${name}\n    ${(err as Error).message}`);
    }
  };

  await test('round-trips signup -> login -> refresh -> logout', async () => {
    const creds = {
      email: 'e2e@example.com',
      password: 'password123',
      role: 'CLINICIAN',
    };

    const s = await gql(SIGNUP, { i: creds });
    assert.equal(s.errors, undefined);
    assert.ok(s.data?.signup.accessToken && s.data?.signup.refreshToken);

    const l = await gql(LOGIN, {
      i: { email: creds.email, password: creds.password },
    });
    assert.equal(l.errors, undefined);
    const refreshToken = l.data?.login.refreshToken as string;
    assert.ok(refreshToken);

    const r = await gql(REFRESH, { rt: refreshToken });
    assert.equal(r.errors, undefined);
    const rotated = r.data?.refresh.refreshToken as string;
    assert.ok(rotated && rotated !== refreshToken);

    const lo = await gql(LOGOUT, { rt: rotated });
    assert.equal(lo.errors, undefined);
    assert.equal(lo.data?.logout, true);

    const r2 = await gql(REFRESH, { rt: rotated });
    assert.ok(r2.errors, 'refresh after logout should be rejected');
  });

  await test('rejects bad login credentials', async () => {
    const res = await gql(LOGIN, {
      i: { email: 'e2e@example.com', password: 'wrong-password' },
    });
    assert.ok(res.errors);
    assert.ok(!res.data?.login);
  });

  await test('duplicate signup returns a sanitized 409 (no stack trace)', async () => {
    const u = {
      email: 'dupe@example.com',
      password: 'password123',
      role: 'PATIENT',
    };

    const first = await gql(SIGNUP, { i: u });
    assert.equal(first.errors, undefined);

    const second = await gql(SIGNUP, { i: u });
    assert.ok(second.errors);
    const err = second.errors![0];
    assert.match(err.message, /already exists/i);
    assert.equal(err.extensions?.statusCode, 409);
    assert.equal(err.extensions?.stacktrace, undefined);
  });

  // ── Eligibility matcher: clinician-only RBAC (ROADMAP step 6) ──────────────
  await test('matchTrials is rejected without authentication', async () => {
    const res = await gql(MATCH_TRIALS, { c: 'melanoma', p: {} });
    assert.ok(res.errors, 'unauthenticated match should be rejected');
    assert.ok(!res.data?.matchTrials);
  });

  await test('matchTrials is forbidden for a non-clinician (PATIENT)', async () => {
    const token = await signupToken('match-patient@example.com', 'PATIENT');
    const res = await gqlAuth(MATCH_TRIALS, { c: 'melanoma', p: {} }, token);
    assert.ok(res.errors, 'PATIENT should be denied');
    assert.match(res.errors![0].message, /insufficient permissions|forbidden/i);
    assert.ok(!res.data?.matchTrials);
  });

  await test('matchTrials passes the role guard for a CLINICIAN', async () => {
    const token = await signupToken('match-clinician@example.com', 'CLINICIAN');
    const res = await gqlAuth(MATCH_TRIALS, { c: 'melanoma', p: {} }, token);
    // The guard lets a clinician through; the call then fails reaching the (unavailable)
    // inference service at SEARCH_API_URL — proving it was NOT blocked on permissions.
    assert.ok(res.errors, 'expected a downstream error (inference unreachable in e2e)');
    assert.doesNotMatch(res.errors![0].message, /insufficient permissions|forbidden/i);
  });

  await app.close();
  await container.stop();

  if (failures > 0) {
    console.error(`\nauth e2e: ${failures} failure(s)`);
    process.exit(1);
  }
  console.log('\nauth e2e: all checks passed');
  process.exit(0);
}

// Use writeSync to fd 2 so the error always reaches the (piped) CI log — console.error
// + process.exit can truncate buffered stdio before it flushes.
function fatal(label: string, err: unknown): never {
  const detail =
    err instanceof Error ? (err.stack ?? err.message) : String(err);
  writeSync(2, `\n[auth-e2e] ${label}:\n${detail}\n`);
  process.exit(1);
}

process.on('unhandledRejection', (err) => fatal('UNHANDLED REJECTION', err));
process.on('uncaughtException', (err) => fatal('UNCAUGHT EXCEPTION', err));

main().catch((err) => fatal('FAILED', err));

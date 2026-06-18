import 'reflect-metadata';
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execSync } from 'node:child_process';
import * as path from 'node:path';
import { NestFactory } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import {
  PostgreSqlContainer,
  StartedPostgreSqlContainer,
} from '@testcontainers/postgresql';
import { AppModule } from '../../src/app.module';

interface GqlResponse {
  data?: Record<string, any>;
  errors?: Array<{ message: string; extensions?: Record<string, unknown> }>;
}

/**
 * Boots the real AppModule (NestJS + Apollo + Prisma) against an ephemeral Postgres and
 * drives the GraphQL auth flow end to end: signup -> login -> refresh -> logout, plus a
 * duplicate-signup that must come back as a sanitized 409 (no stack trace).
 *
 * Requires Docker. Run with: pnpm --filter api-core test:integration
 */
describe('Auth GraphQL (e2e · real Postgres)', () => {
  let container: StartedPostgreSqlContainer;
  let app: NestFastifyApplication;

  async function gql(
    query: string,
    variables: Record<string, unknown> = {},
  ): Promise<GqlResponse> {
    const res = await app.inject({
      method: 'POST',
      url: '/graphql',
      headers: { 'content-type': 'application/json' },
      payload: JSON.stringify({ query, variables }),
    });
    return res.json() as GqlResponse;
  }

  beforeAll(async () => {
    container = await new PostgreSqlContainer('postgres:16-alpine').start();
    const url = container.getConnectionUri();

    const dbDir = path.resolve(__dirname, '../../../../packages/db');
    execSync('npx prisma db push --accept-data-loss', {
      cwd: dbDir,
      env: { ...process.env, DATABASE_URL: url },
      stdio: 'inherit',
    });

    // process.env takes precedence over the .env file in @nestjs/config, so this points
    // the booting app at the container and supplies the auth config it needs to start.
    process.env.DATABASE_URL = url;
    process.env.JWT_SECRET = 'test-secret';
    process.env.JWT_EXPIRES_IN = '15m';
    process.env.REFRESH_TOKEN_TTL_DAYS = '30';

    app = await NestFactory.create<NestFastifyApplication>(
      AppModule,
      new FastifyAdapter(),
      { logger: false },
    );
    await app.init();
    await app.getHttpAdapter().getInstance().ready();
  }, 180_000);

  afterAll(async () => {
    await app?.close();
    await container?.stop();
  });

  const SIGNUP =
    'mutation($i:SignupInput!){signup(input:$i){accessToken refreshToken}}';
  const LOGIN =
    'mutation($i:LoginInput!){login(input:$i){accessToken refreshToken}}';
  const REFRESH =
    'mutation($rt:String!){refresh(refreshToken:$rt){accessToken refreshToken}}';
  const LOGOUT = 'mutation($rt:String!){logout(refreshToken:$rt)}';

  it('round-trips signup -> login -> refresh -> logout through GraphQL', async () => {
    const creds = {
      username: 'e2euser',
      email: 'e2e@example.com',
      password: 'password123',
      role: 'CLINICIAN',
    };

    const s = await gql(SIGNUP, { i: creds });
    expect(s.errors).toBeUndefined();
    expect(s.data?.signup.accessToken).toBeTruthy();
    expect(s.data?.signup.refreshToken).toBeTruthy();

    const l = await gql(LOGIN, {
      i: { username: creds.username, password: creds.password },
    });
    expect(l.errors).toBeUndefined();
    const refreshToken = l.data?.login.refreshToken as string;
    expect(refreshToken).toBeTruthy();

    const r = await gql(REFRESH, { rt: refreshToken });
    expect(r.errors).toBeUndefined();
    const rotated = r.data?.refresh.refreshToken as string;
    expect(rotated).toBeTruthy();
    expect(rotated).not.toBe(refreshToken); // rotated

    const lo = await gql(LOGOUT, { rt: rotated });
    expect(lo.errors).toBeUndefined();
    expect(lo.data?.logout).toBe(true);

    // the rotated token is now revoked
    const r2 = await gql(REFRESH, { rt: rotated });
    expect(r2.errors).toBeTruthy();
  });

  it('rejects bad login credentials', async () => {
    const res = await gql(LOGIN, {
      i: { username: 'e2euser', password: 'wrong-password' },
    });
    expect(res.errors).toBeTruthy();
    expect(res.data?.login).toBeFalsy();
  });

  it('returns a sanitized 409 for a duplicate signup (no stack trace)', async () => {
    const u = {
      username: 'dupe',
      email: 'dupe@example.com',
      password: 'password123',
      role: 'PATIENT',
    };

    const first = await gql(SIGNUP, { i: u });
    expect(first.errors).toBeUndefined();

    const second = await gql(SIGNUP, { i: u });
    expect(second.errors).toBeTruthy();
    const err = second.errors![0];
    expect(err.message).toMatch(/already exists/i);
    expect(err.extensions?.statusCode).toBe(409);
    // formatError must strip the stack trace.
    expect(err.extensions?.stacktrace).toBeUndefined();
  });
});

import 'reflect-metadata'; // required: SessionService's @Injectable() runs at import
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execSync } from 'node:child_process';
import * as path from 'node:path';
import { createHash } from 'node:crypto';
import {
  PostgreSqlContainer,
  StartedPostgreSqlContainer,
} from '@testcontainers/postgresql';
import { ConfigService } from '@nestjs/config';
import { createPrismaClient, PrismaClient } from '@repo/db';
import { PrismaService } from '../../src/prisma/prisma.service';
import { SessionService } from '../../src/auth/session.service';

const sha256 = (s: string) => createHash('sha256').update(s).digest('hex');

/**
 * Exercises the real SQL + transaction paths of SessionService against an ephemeral
 * Postgres (Testcontainers). Complements the mocked unit tests by verifying the actual
 * Prisma queries, the `app` schema, and that rotate() is atomic.
 *
 * Requires Docker. Run with: pnpm --filter api-core test:integration
 */
describe('SessionService (integration · real Postgres)', () => {
  let container: StartedPostgreSqlContainer;
  let prisma: PrismaClient;
  let service: SessionService;

  beforeAll(async () => {
    container = await new PostgreSqlContainer('postgres:16-alpine').start();
    const url = container.getConnectionUri();

    // Build the `app` schema (User + Session + enums) from the Prisma schema.
    // dotenv in prisma.config.ts won't override DATABASE_URL since we pass it.
    const dbDir = path.resolve(__dirname, '../../../../packages/db');
    execSync('npx prisma db push --accept-data-loss', {
      cwd: dbDir,
      env: { ...process.env, DATABASE_URL: url },
      stdio: 'inherit',
    });

    prisma = createPrismaClient(url);
    const prismaService = { client: prisma } as unknown as PrismaService;
    const config = { get: () => '30' } as unknown as ConfigService;
    service = new SessionService(prismaService, config);
  }, 180_000);

  afterAll(async () => {
    await prisma?.$disconnect();
    await container?.stop();
  });

  // Fresh user per test so each test's session state is isolated.
  async function newUser(): Promise<string> {
    const suffix = `${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const user = await prisma.user.create({
      data: {
        username: `it_${suffix}`,
        email: `it_${suffix}@example.com`,
        passwordHash: 'x',
      },
    });
    return user.id;
  }

  it('issue: stores only the token hash; the raw token is never persisted', async () => {
    const userId = await newUser();
    const raw = await service.issue(userId, { userAgent: 'jest', ip: '127.0.0.1' });

    const byHash = await prisma.session.findUnique({
      where: { tokenHash: sha256(raw) },
    });
    expect(byHash?.userId).toBe(userId);
    expect(byHash?.userAgent).toBe('jest');

    const byRaw = await prisma.session.findUnique({ where: { tokenHash: raw } });
    expect(byRaw).toBeNull();
  });

  it('rotate: atomically revokes the old session and activates exactly one new one', async () => {
    const userId = await newUser();
    const raw = await service.issue(userId);

    const { refreshToken: newRaw } = await service.rotate(raw);

    const oldRow = await prisma.session.findUnique({
      where: { tokenHash: sha256(raw) },
    });
    const newRow = await prisma.session.findUnique({
      where: { tokenHash: sha256(newRaw) },
    });
    expect(oldRow?.revokedAt).not.toBeNull();
    expect(newRow?.revokedAt).toBeNull();

    const active = await prisma.session.count({
      where: { userId, revokedAt: null },
    });
    expect(active).toBe(1);
  });

  it('reuse detection: replaying a rotated token revokes ALL the user sessions', async () => {
    const userId = await newUser();
    const raw = await service.issue(userId);
    await service.rotate(raw); // raw is now revoked; a new session is active

    await expect(service.rotate(raw)).rejects.toThrow();

    const active = await prisma.session.count({
      where: { userId, revokedAt: null },
    });
    expect(active).toBe(0);
  });

  it('expired token is rejected and nothing is rotated', async () => {
    const userId = await newUser();
    const raw = 'expired-raw-token';
    await prisma.session.create({
      data: {
        userId,
        tokenHash: sha256(raw),
        expiresAt: new Date(Date.now() - 1000),
      },
    });

    await expect(service.rotate(raw)).rejects.toThrow();
    // The expired session is untouched; no new session created.
    const total = await prisma.session.count({ where: { userId } });
    expect(total).toBe(1);
  });

  it('revoke: marks the matching session revoked', async () => {
    const userId = await newUser();
    const raw = await service.issue(userId);

    await service.revoke(raw);

    const row = await prisma.session.findUnique({
      where: { tokenHash: sha256(raw) },
    });
    expect(row?.revokedAt).not.toBeNull();
  });
});

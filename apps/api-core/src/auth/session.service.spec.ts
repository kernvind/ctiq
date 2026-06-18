import { createHash } from 'node:crypto';
import { UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma/prisma.service';
import { SessionService } from './session.service';

const sha256 = (s: string) => createHash('sha256').update(s).digest('hex');

describe('SessionService', () => {
  let service: SessionService;
  let session: {
    create: jest.Mock;
    findUnique: jest.Mock;
    update: jest.Mock;
    updateMany: jest.Mock;
  };
  let prisma: PrismaService;

  beforeEach(() => {
    session = {
      create: jest.fn().mockResolvedValue({}),
      findUnique: jest.fn(),
      update: jest.fn().mockResolvedValue({}),
      updateMany: jest.fn().mockResolvedValue({ count: 1 }),
    };
    prisma = {
      client: {
        session,
        $transaction: jest.fn((ops: unknown[]) => Promise.all(ops)),
      },
    } as unknown as PrismaService;
    const config = {
      get: jest.fn().mockReturnValue('30'),
    } as unknown as ConfigService;
    service = new SessionService(prisma, config);
  });

  describe('issue', () => {
    it('stores only the hash of the token and returns the raw token', async () => {
      const raw = await service.issue('user-1', {
        userAgent: 'jest',
        ip: '1.2.3.4',
      });

      expect(typeof raw).toBe('string');
      expect(raw.length).toBeGreaterThan(0);
      expect(session.create).toHaveBeenCalledTimes(1);

      const data = session.create.mock.calls[0][0].data;
      expect(data.userId).toBe('user-1');
      expect(data.userAgent).toBe('jest');
      expect(data.ip).toBe('1.2.3.4');
      // The stored value is the hash, never the raw token.
      expect(data.tokenHash).toBe(sha256(raw));
      expect(data.tokenHash).not.toBe(raw);
      expect(data.expiresAt.getTime()).toBeGreaterThan(Date.now());
    });
  });

  describe('rotate', () => {
    const validSession = (over: Record<string, unknown> = {}) => ({
      id: 's1',
      userId: 'user-1',
      tokenHash: 'whatever',
      revokedAt: null,
      expiresAt: new Date(Date.now() + 60_000),
      ...over,
    });

    it('revokes the old session, issues a new one, and returns a fresh token', async () => {
      session.findUnique.mockResolvedValue(validSession());

      const result = await service.rotate('old-raw-token');

      // old session revoked + new session created within one transaction
      expect(prisma.client.$transaction).toHaveBeenCalledTimes(1);
      expect(session.update).toHaveBeenCalledWith({
        where: { id: 's1' },
        data: { revokedAt: expect.any(Date) },
      });
      expect(session.create).toHaveBeenCalledTimes(1);

      expect(result.userId).toBe('user-1');
      expect(result.refreshToken).not.toBe('old-raw-token');
      // new session stored as the hash of the returned token
      const newData = session.create.mock.calls[0][0].data;
      expect(newData.tokenHash).toBe(sha256(result.refreshToken));
    });

    it('rejects an unknown token without revoking anything', async () => {
      session.findUnique.mockResolvedValue(null);

      await expect(service.rotate('nope')).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
      expect(session.updateMany).not.toHaveBeenCalled();
      expect(prisma.client.$transaction).not.toHaveBeenCalled();
    });

    it('treats reuse of a revoked token as theft and revokes ALL the user sessions', async () => {
      session.findUnique.mockResolvedValue(
        validSession({ revokedAt: new Date() }),
      );

      await expect(service.rotate('reused')).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
      // revokeAllForUser
      expect(session.updateMany).toHaveBeenCalledWith({
        where: { userId: 'user-1', revokedAt: null },
        data: { revokedAt: expect.any(Date) },
      });
      // no rotation happened
      expect(prisma.client.$transaction).not.toHaveBeenCalled();
    });

    it('rejects an expired token', async () => {
      session.findUnique.mockResolvedValue(
        validSession({ expiresAt: new Date(Date.now() - 1000) }),
      );

      await expect(service.rotate('old')).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
      expect(prisma.client.$transaction).not.toHaveBeenCalled();
      expect(session.updateMany).not.toHaveBeenCalled();
    });
  });

  describe('revoke', () => {
    it('revokes the single session matching the token hash', async () => {
      await service.revoke('some-token');

      expect(session.updateMany).toHaveBeenCalledWith({
        where: { tokenHash: sha256('some-token'), revokedAt: null },
        data: { revokedAt: expect.any(Date) },
      });
    });
  });
});

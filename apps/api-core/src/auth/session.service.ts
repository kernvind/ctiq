import { createHash, randomBytes } from 'node:crypto';
import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../prisma/prisma.service';

export interface SessionMeta {
  userAgent?: string | null;
  ip?: string | null;
}

/**
 * Refresh-token sessions. Tokens are opaque high-entropy strings; only their SHA-256
 * hash is stored (never the raw token). Tokens are rotated on every use, and reuse of
 * an already-rotated token triggers revocation of all the user's sessions (theft
 * defense).
 */
@Injectable()
export class SessionService {
  private readonly logger = new Logger(SessionService.name);
  private readonly refreshTtlMs: number;

  constructor(
    private readonly prisma: PrismaService,
    config: ConfigService,
  ) {
    const days = Number(config.get<string>('REFRESH_TOKEN_TTL_DAYS') ?? '30');
    this.refreshTtlMs = days * 24 * 60 * 60 * 1000;
  }

  private hash(rawToken: string): string {
    return createHash('sha256').update(rawToken).digest('hex');
  }

  private newRawToken(): string {
    return randomBytes(32).toString('base64url');
  }

  /** Create a session and return the raw refresh token (stored only as a hash). */
  async issue(userId: string, meta: SessionMeta = {}): Promise<string> {
    const rawToken = this.newRawToken();
    const expiresAt = new Date(Date.now() + this.refreshTtlMs);
    await this.prisma.client.session.create({
      data: {
        userId,
        tokenHash: this.hash(rawToken),
        expiresAt,
        userAgent: meta.userAgent ?? null,
        ip: meta.ip ?? null,
      },
    });
    this.logger.log(
      `session issued userId=${userId} expiresAt=${expiresAt.toISOString()}`,
    );
    return rawToken;
  }

  /**
   * Validate and rotate a refresh token: the presented session is revoked and a fresh
   * one issued. Returns the owning userId and the new raw refresh token.
   */
  async rotate(
    rawToken: string,
    meta: SessionMeta = {},
  ): Promise<{ userId: string; refreshToken: string }> {
    const session = await this.prisma.client.session.findUnique({
      where: { tokenHash: this.hash(rawToken) },
    });

    if (!session) {
      this.logger.warn('refresh rejected: unknown token');
      throw new UnauthorizedException('Invalid refresh token');
    }
    if (session.revokedAt) {
      // A revoked token being presented means it was already rotated — likely theft.
      // Defensively revoke every session for the user.
      this.logger.warn(
        `refresh rejected: reuse of revoked token sessionId=${session.id} ` +
          `userId=${session.userId} -> revoking all user sessions`,
      );
      await this.revokeAllForUser(session.userId);
      throw new UnauthorizedException('Invalid refresh token');
    }
    if (session.expiresAt.getTime() <= Date.now()) {
      this.logger.warn(
        `refresh rejected: expired sessionId=${session.id} userId=${session.userId}`,
      );
      throw new UnauthorizedException('Refresh token expired');
    }

    const newRaw = this.newRawToken();
    const expiresAt = new Date(Date.now() + this.refreshTtlMs);
    await this.prisma.client.$transaction([
      this.prisma.client.session.update({
        where: { id: session.id },
        data: { revokedAt: new Date() },
      }),
      this.prisma.client.session.create({
        data: {
          userId: session.userId,
          tokenHash: this.hash(newRaw),
          expiresAt,
          userAgent: meta.userAgent ?? null,
          ip: meta.ip ?? null,
        },
      }),
    ]);
    this.logger.log(
      `session rotated userId=${session.userId} oldSessionId=${session.id}`,
    );
    return { userId: session.userId, refreshToken: newRaw };
  }

  /** Revoke the single session tied to a refresh token (logout, current session only). */
  async revoke(rawToken: string): Promise<void> {
    const result = await this.prisma.client.session.updateMany({
      where: { tokenHash: this.hash(rawToken), revokedAt: null },
      data: { revokedAt: new Date() },
    });
    this.logger.log(`session revoked count=${result.count}`);
  }

  private async revokeAllForUser(userId: string): Promise<void> {
    const result = await this.prisma.client.session.updateMany({
      where: { userId, revokedAt: null },
      data: { revokedAt: new Date() },
    });
    this.logger.warn(
      `revoked all sessions userId=${userId} count=${result.count}`,
    );
  }
}

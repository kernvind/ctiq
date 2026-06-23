import { Injectable } from '@nestjs/common';
import { Prisma } from '@repo/db';
import { PrismaService } from '../prisma/prisma.service';

export interface LandscapeSpecValue {
  q: string;
  phase?: string | null;
}

export interface CreateLandscapeArgs {
  name: string;
  q: string;
  phase?: string | null;
}

export interface LandscapeRecord {
  id: string;
  userId: string;
  name: string;
  spec: unknown;
  lastSeenNctIds: string[];
  lastCheckedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

@Injectable()
export class LandscapesService {
  constructor(private readonly prisma: PrismaService) {}

  async create(
    userId: string,
    args: CreateLandscapeArgs,
  ): Promise<LandscapeRecord> {
    const spec: LandscapeSpecValue = { q: args.q, phase: args.phase ?? null };
    return this.prisma.client.landscape.create({
      data: {
        userId,
        name: args.name,
        spec: spec as unknown as Prisma.InputJsonValue,
      },
    });
  }

  async listForUser(userId: string): Promise<LandscapeRecord[]> {
    return this.prisma.client.landscape.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }

  async remove(userId: string, id: string): Promise<boolean> {
    // Scope by userId so a user can only delete their own landscape.
    const { count } = await this.prisma.client.landscape.deleteMany({
      where: { id, userId },
    });
    return count > 0;
  }

  /** Update a landscape's monitoring snapshot after the client runs it. */
  async markSeen(
    userId: string,
    id: string,
    nctIds: string[],
  ): Promise<LandscapeRecord | null> {
    const { count } = await this.prisma.client.landscape.updateMany({
      where: { id, userId },
      data: { lastSeenNctIds: nctIds, lastCheckedAt: new Date() },
    });
    if (count === 0) return null;
    return this.prisma.client.landscape.findFirst({ where: { id, userId } });
  }
}

import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface PortfolioTrialRecord {
  id: string;
  userId: string;
  nctId: string;
  createdAt: Date;
}

@Injectable()
export class PortfolioService {
  constructor(private readonly prisma: PrismaService) {}

  /** Add a trial to a user's open-trial portfolio. Idempotent — re-adding is a no-op. */
  async add(userId: string, nctId: string): Promise<PortfolioTrialRecord> {
    return this.prisma.client.portfolioTrial.upsert({
      where: { userId_nctId: { userId, nctId } },
      create: { userId, nctId },
      update: {},
    });
  }

  /** Remove a trial from the portfolio. Returns whether a row was actually deleted. */
  async remove(userId: string, nctId: string): Promise<boolean> {
    const { count } = await this.prisma.client.portfolioTrial.deleteMany({
      where: { userId, nctId },
    });
    return count > 0;
  }

  /** A user's portfolio trials, most recently added first. */
  async listForUser(userId: string): Promise<PortfolioTrialRecord[]> {
    return this.prisma.client.portfolioTrial.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }

  /** Just the NCT ids in a user's portfolio — the candidate set for portfolio screening. */
  async nctIdsForUser(userId: string): Promise<string[]> {
    const rows = await this.prisma.client.portfolioTrial.findMany({
      where: { userId },
      select: { nctId: true },
    });
    return rows.map((r) => r.nctId);
  }
}

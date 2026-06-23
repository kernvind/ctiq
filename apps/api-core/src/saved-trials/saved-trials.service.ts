import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface SavedTrialRecord {
  id: string;
  userId: string;
  nctId: string;
  createdAt: Date;
}

@Injectable()
export class SavedTrialsService {
  constructor(private readonly prisma: PrismaService) {}

  /** Save a trial for a user. Idempotent — saving an already-saved trial is a no-op. */
  async save(userId: string, nctId: string): Promise<SavedTrialRecord> {
    return this.prisma.client.savedTrial.upsert({
      where: { userId_nctId: { userId, nctId } },
      create: { userId, nctId },
      update: {},
    });
  }

  /** Remove a saved trial. Returns whether a row was actually deleted. */
  async remove(userId: string, nctId: string): Promise<boolean> {
    const { count } = await this.prisma.client.savedTrial.deleteMany({
      where: { userId, nctId },
    });
    return count > 0;
  }

  /** A user's saved trials, most recently saved first. */
  async listForUser(userId: string): Promise<SavedTrialRecord[]> {
    return this.prisma.client.savedTrial.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
    });
  }
}

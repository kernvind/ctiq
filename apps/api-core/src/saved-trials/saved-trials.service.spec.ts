import { PrismaService } from '../prisma/prisma.service';
import { SavedTrialsService } from './saved-trials.service';

describe('SavedTrialsService', () => {
  let service: SavedTrialsService;
  let savedTrial: {
    upsert: jest.Mock;
    deleteMany: jest.Mock;
    findMany: jest.Mock;
  };

  beforeEach(() => {
    savedTrial = {
      upsert: jest.fn(),
      deleteMany: jest.fn(),
      findMany: jest.fn(),
    };
    const prisma = { client: { savedTrial } } as unknown as PrismaService;
    service = new SavedTrialsService(prisma);
  });

  describe('save', () => {
    it('upserts on the (userId, nctId) unique key so saving is idempotent', async () => {
      const row = { id: 's1', userId: 'u1', nctId: 'NCT01', createdAt: new Date() };
      savedTrial.upsert.mockResolvedValue(row);

      const result = await service.save('u1', 'NCT01');

      expect(savedTrial.upsert).toHaveBeenCalledWith({
        where: { userId_nctId: { userId: 'u1', nctId: 'NCT01' } },
        create: { userId: 'u1', nctId: 'NCT01' },
        update: {},
      });
      expect(result).toBe(row);
    });
  });

  describe('remove', () => {
    it('returns true when a row was deleted', async () => {
      savedTrial.deleteMany.mockResolvedValue({ count: 1 });

      expect(await service.remove('u1', 'NCT01')).toBe(true);
      expect(savedTrial.deleteMany).toHaveBeenCalledWith({
        where: { userId: 'u1', nctId: 'NCT01' },
      });
    });

    it('returns false when nothing matched', async () => {
      savedTrial.deleteMany.mockResolvedValue({ count: 0 });

      expect(await service.remove('u1', 'NCT01')).toBe(false);
    });
  });

  describe('listForUser', () => {
    it("returns the user's saved trials, most recent first", async () => {
      const rows = [{ id: 's2' }, { id: 's1' }];
      savedTrial.findMany.mockResolvedValue(rows);

      const result = await service.listForUser('u1');

      expect(savedTrial.findMany).toHaveBeenCalledWith({
        where: { userId: 'u1' },
        orderBy: { createdAt: 'desc' },
      });
      expect(result).toBe(rows);
    });
  });
});

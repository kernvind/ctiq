import { PrismaService } from '../prisma/prisma.service';
import { PortfolioService } from './portfolio.service';

describe('PortfolioService', () => {
  let service: PortfolioService;
  let portfolioTrial: {
    upsert: jest.Mock;
    deleteMany: jest.Mock;
    findMany: jest.Mock;
  };

  beforeEach(() => {
    portfolioTrial = {
      upsert: jest.fn(),
      deleteMany: jest.fn(),
      findMany: jest.fn(),
    };
    const prisma = { client: { portfolioTrial } } as unknown as PrismaService;
    service = new PortfolioService(prisma);
  });

  describe('add', () => {
    it('upserts on (userId, nctId) so adding is idempotent', async () => {
      const row = {
        id: 'p1',
        userId: 'u1',
        nctId: 'NCT01',
        createdAt: new Date(),
      };
      portfolioTrial.upsert.mockResolvedValue(row);

      const result = await service.add('u1', 'NCT01');

      expect(portfolioTrial.upsert).toHaveBeenCalledWith({
        where: { userId_nctId: { userId: 'u1', nctId: 'NCT01' } },
        create: { userId: 'u1', nctId: 'NCT01' },
        update: {},
      });
      expect(result).toBe(row);
    });
  });

  describe('remove', () => {
    it('returns true when a row was deleted, false otherwise', async () => {
      portfolioTrial.deleteMany.mockResolvedValueOnce({ count: 1 });
      await expect(service.remove('u1', 'NCT01')).resolves.toBe(true);

      portfolioTrial.deleteMany.mockResolvedValueOnce({ count: 0 });
      await expect(service.remove('u1', 'NCT99')).resolves.toBe(false);
    });
  });

  describe('nctIdsForUser', () => {
    it('returns just the NCT ids (the screening candidate set)', async () => {
      portfolioTrial.findMany.mockResolvedValue([
        { nctId: 'NCT01' },
        { nctId: 'NCT02' },
      ]);

      await expect(service.nctIdsForUser('u1')).resolves.toEqual([
        'NCT01',
        'NCT02',
      ]);
      expect(portfolioTrial.findMany).toHaveBeenCalledWith({
        where: { userId: 'u1' },
        select: { nctId: true },
      });
    });
  });
});

import { PrismaService } from '../prisma/prisma.service';
import { LandscapesService } from './landscapes.service';

describe('LandscapesService', () => {
  let service: LandscapesService;
  let landscape: {
    create: jest.Mock;
    findMany: jest.Mock;
    deleteMany: jest.Mock;
    updateMany: jest.Mock;
    findFirst: jest.Mock;
  };

  beforeEach(() => {
    landscape = {
      create: jest.fn(),
      findMany: jest.fn(),
      deleteMany: jest.fn(),
      updateMany: jest.fn(),
      findFirst: jest.fn(),
    };
    const prisma = { client: { landscape } } as unknown as PrismaService;
    service = new LandscapesService(prisma);
  });

  describe('create', () => {
    it('stores the query + phase as the agent-ready JSON spec', async () => {
      const row = { id: 'l1' };
      landscape.create.mockResolvedValue(row);

      await service.create('u1', {
        name: 'GLP-1 obesity',
        q: 'phase 3 GLP-1 obesity trials',
        phase: 'PHASE3',
      });

      expect(landscape.create).toHaveBeenCalledWith({
        data: {
          userId: 'u1',
          name: 'GLP-1 obesity',
          spec: { q: 'phase 3 GLP-1 obesity trials', phase: 'PHASE3' },
        },
      });
    });

    it('defaults phase to null when omitted', async () => {
      landscape.create.mockResolvedValue({});
      await service.create('u1', { name: 'n', q: 'a long enough query' });
      expect(landscape.create).toHaveBeenCalledWith({
        data: {
          userId: 'u1',
          name: 'n',
          spec: { q: 'a long enough query', phase: null },
        },
      });
    });
  });

  describe('remove', () => {
    it('scopes the delete to the owner and returns whether a row went', async () => {
      landscape.deleteMany.mockResolvedValue({ count: 1 });

      expect(await service.remove('u1', 'l1')).toBe(true);
      expect(landscape.deleteMany).toHaveBeenCalledWith({
        where: { id: 'l1', userId: 'u1' },
      });
    });

    it('returns false when nothing matched (e.g. not the owner)', async () => {
      landscape.deleteMany.mockResolvedValue({ count: 0 });
      expect(await service.remove('u1', 'l1')).toBe(false);
    });
  });

  describe('markSeen', () => {
    it('updates the snapshot (owner-scoped) and returns the refreshed row', async () => {
      landscape.updateMany.mockResolvedValue({ count: 1 });
      const row = { id: 'l1', lastSeenNctIds: ['NCT1', 'NCT2'] };
      landscape.findFirst.mockResolvedValue(row);

      const result = await service.markSeen('u1', 'l1', ['NCT1', 'NCT2']);

      expect(landscape.updateMany).toHaveBeenCalledWith({
        where: { id: 'l1', userId: 'u1' },
        data: { lastSeenNctIds: ['NCT1', 'NCT2'], lastCheckedAt: expect.any(Date) },
      });
      expect(result).toBe(row);
    });

    it('returns null without refetching when no landscape matched', async () => {
      landscape.updateMany.mockResolvedValue({ count: 0 });

      expect(await service.markSeen('u1', 'nope', [])).toBeNull();
      expect(landscape.findFirst).not.toHaveBeenCalled();
    });
  });
});

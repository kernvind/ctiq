import { Role } from '@repo/db';
import { LandscapesResolver } from './landscapes.resolver';
import { AuthedUser } from '../auth/decorators/current-user.decorator';
import { LandscapeRecord } from './landscapes.service';

const user: AuthedUser = { id: 'u1', email: 'a@example.com', role: Role.ANALYST };

const record = (over: Partial<LandscapeRecord> = {}): LandscapeRecord => ({
  id: 'l1',
  userId: 'u1',
  name: 'GLP-1 obesity',
  spec: { q: 'phase 3 GLP-1 obesity trials', phase: 'PHASE3' },
  lastSeenNctIds: ['NCT1'],
  lastCheckedAt: null,
  createdAt: new Date('2026-06-22T00:00:00Z'),
  updatedAt: new Date('2026-06-22T00:00:00Z'),
  ...over,
});

describe('LandscapesResolver', () => {
  let resolver: LandscapesResolver;
  let service: {
    listForUser: jest.Mock;
    create: jest.Mock;
    remove: jest.Mock;
    markSeen: jest.Mock;
  };

  beforeEach(() => {
    service = {
      listForUser: jest.fn(),
      create: jest.fn(),
      remove: jest.fn(),
      markSeen: jest.fn(),
    };
    resolver = new LandscapesResolver(service as never);
  });

  it('maps the JSON spec to the typed LandscapeSpec when listing', async () => {
    service.listForUser.mockResolvedValue([record()]);

    const [landscape] = await resolver.landscapes(user);

    expect(service.listForUser).toHaveBeenCalledWith('u1');
    expect(landscape.spec).toEqual({
      q: 'phase 3 GLP-1 obesity trials',
      phase: 'PHASE3',
    });
    expect(landscape.lastSeenNctIds).toEqual(['NCT1']);
  });

  it('defaults a missing/empty spec to safe values', async () => {
    service.listForUser.mockResolvedValue([
      record({ spec: {}, lastSeenNctIds: undefined as never }),
    ]);

    const [landscape] = await resolver.landscapes(user);

    expect(landscape.spec).toEqual({ q: '', phase: null });
    expect(landscape.lastSeenNctIds).toEqual([]);
  });

  it('createLandscape forwards the input fields scoped to the user', async () => {
    service.create.mockResolvedValue(record());

    await resolver.createLandscape(user, {
      name: 'GLP-1 obesity',
      q: 'phase 3 GLP-1 obesity trials',
      phase: 'PHASE3',
    });

    expect(service.create).toHaveBeenCalledWith('u1', {
      name: 'GLP-1 obesity',
      q: 'phase 3 GLP-1 obesity trials',
      phase: 'PHASE3',
    });
  });

  it('deleteLandscape removes the user-scoped landscape', async () => {
    service.remove.mockResolvedValue(true);

    await expect(resolver.deleteLandscape(user, 'l1')).resolves.toBe(true);
    expect(service.remove).toHaveBeenCalledWith('u1', 'l1');
  });

  it('markLandscapeSeen returns null when the landscape is not the user\'s', async () => {
    service.markSeen.mockResolvedValue(null);

    await expect(
      resolver.markLandscapeSeen(user, 'l1', ['NCT1']),
    ).resolves.toBeNull();
    expect(service.markSeen).toHaveBeenCalledWith('u1', 'l1', ['NCT1']);
  });
});

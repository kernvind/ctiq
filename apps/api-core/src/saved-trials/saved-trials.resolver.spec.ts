import { Role } from '@repo/db';
import { SavedTrialsResolver } from './saved-trials.resolver';
import { AuthedUser } from '../auth/decorators/current-user.decorator';

const user: AuthedUser = {
  id: 'u1',
  email: 'a@example.com',
  role: Role.ANALYST,
};

describe('SavedTrialsResolver', () => {
  let resolver: SavedTrialsResolver;
  let service: { listForUser: jest.Mock; save: jest.Mock; remove: jest.Mock };

  beforeEach(() => {
    service = {
      listForUser: jest.fn(),
      save: jest.fn(),
      remove: jest.fn(),
    };
    resolver = new SavedTrialsResolver(service as never);
  });

  it('savedTrials lists the current user\'s saved trials', async () => {
    const rows = [{ id: 's1' }];
    service.listForUser.mockResolvedValue(rows);

    await expect(resolver.savedTrials(user)).resolves.toBe(rows);
    expect(service.listForUser).toHaveBeenCalledWith('u1');
  });

  it('saveTrial normalizes the nct id to upper-case and scopes to the user', async () => {
    const row = { id: 's1', nctId: 'NCT00000001' };
    service.save.mockResolvedValue(row);

    await resolver.saveTrial(user, 'nct00000001');

    expect(service.save).toHaveBeenCalledWith('u1', 'NCT00000001');
  });

  it('unsaveTrial removes the user-scoped, upper-cased trial', async () => {
    service.remove.mockResolvedValue(true);

    await expect(resolver.unsaveTrial(user, 'nct00000001')).resolves.toBe(true);
    expect(service.remove).toHaveBeenCalledWith('u1', 'NCT00000001');
  });
});

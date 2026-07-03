import { Role } from '@repo/db';
import { EligibilityMatchResolver } from './eligibility-match.resolver';
import { ROLES_KEY } from '../auth/decorators/roles.decorator';
import type { PatientProfileInput } from '@repo/graphql-types';

const profile = {
  ecog: 1,
  biomarkers: [],
  prior_therapies: [],
  labs: [],
  washouts: [],
} as PatientProfileInput;

describe('EligibilityMatchResolver', () => {
  let resolver: EligibilityMatchResolver;
  let service: {
    matchTrial: jest.Mock;
    matchTrials: jest.Mock;
    screenPortfolio: jest.Mock;
  };
  let portfolio: { nctIdsForUser: jest.Mock };

  beforeEach(() => {
    service = {
      matchTrial: jest.fn(),
      matchTrials: jest.fn(),
      screenPortfolio: jest.fn(),
    };
    portfolio = { nctIdsForUser: jest.fn() };
    resolver = new EligibilityMatchResolver(
      service as never,
      portfolio as never,
    );
  });

  it('is gated to the CLINICIAN role (locks the clinician-only product rule)', () => {
    const roles = Reflect.getMetadata(ROLES_KEY, EligibilityMatchResolver);
    expect(roles).toEqual([Role.CLINICIAN]);
  });

  it('matchTrial delegates to the service with nctId + profile', async () => {
    const result = { nct_id: 'NCT01234567', signal: 'likely_eligible' };
    service.matchTrial.mockResolvedValue(result);

    await expect(resolver.matchTrial('NCT01234567', profile)).resolves.toBe(result);
    expect(service.matchTrial).toHaveBeenCalledWith('NCT01234567', profile);
  });

  it('matchTrials delegates to the service with condition, profile, topK, recruitingOnly', async () => {
    const ranked = [{ nct_id: 'NCT1', signal: 'likely_eligible' }];
    service.matchTrials.mockResolvedValue(ranked);

    await expect(resolver.matchTrials('melanoma', profile, 25, false)).resolves.toBe(ranked);
    expect(service.matchTrials).toHaveBeenCalledWith('melanoma', profile, 25, false);
  });

  it('screenPortfolio loads the user\'s portfolio NCT ids and forwards them with the profile', async () => {
    const ranked = [{ nct_id: 'NCT1', signal: 'likely_excluded' }];
    portfolio.nctIdsForUser.mockResolvedValue(['NCT1', 'NCT2']);
    service.screenPortfolio.mockResolvedValue(ranked);

    const user = { id: 'user-123' } as never;
    await expect(resolver.screenPortfolio(user, profile)).resolves.toBe(ranked);
    expect(portfolio.nctIdsForUser).toHaveBeenCalledWith('user-123');
    expect(service.screenPortfolio).toHaveBeenCalledWith(['NCT1', 'NCT2'], profile);
  });
});

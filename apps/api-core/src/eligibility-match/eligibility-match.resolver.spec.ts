import { Role } from '@repo/db';
import { EligibilityMatchResolver } from './eligibility-match.resolver';
import { ROLES_KEY } from '../auth/decorators/roles.decorator';
import type { PatientProfileInput } from '@repo/graphql-types';

const profile = { ecog: 1, biomarkers: [], prior_therapies: [], labs: [] } as PatientProfileInput;

describe('EligibilityMatchResolver', () => {
  let resolver: EligibilityMatchResolver;
  let service: { matchTrial: jest.Mock; matchTrials: jest.Mock };

  beforeEach(() => {
    service = { matchTrial: jest.fn(), matchTrials: jest.fn() };
    resolver = new EligibilityMatchResolver(service as never);
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
});

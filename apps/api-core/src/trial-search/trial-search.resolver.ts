import { Args, Query, Resolver } from '@nestjs/graphql';
import { TrialSearchService } from './trial-search.service';
import { SearchTrialInput, TrialCard, TrialDetail } from '@repo/graphql-types';
import { ZodTrialSearchSchema, ZodNctIdSchema } from '@repo/zod-validations';
import { zodPipe } from '../common/pipes/zod-validation.pipe';

@Resolver()
export class TrialSearchResolver {
  constructor(private readonly trialSearchService: TrialSearchService) {}

  @Query(() => [TrialCard])
  async searchTrials(
    @Args('q', zodPipe(ZodTrialSearchSchema)) input: SearchTrialInput,
  ): Promise<TrialCard[]> {
    return this.trialSearchService.searchTrials(input.q);
  }

  // Trial detail. Public data (no auth guard) so it can also serve the future
  // no-account surface. Returns null when the NCT id has no matching trial.
  @Query(() => TrialDetail, { nullable: true })
  async trial(
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
  ): Promise<TrialDetail | null> {
    return this.trialSearchService.getTrial(nctId);
  }
}

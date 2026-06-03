import { Args, Query, Resolver } from '@nestjs/graphql';
import { TrialSearchService } from './trial-search.service';
import { SearchTrialInput, TrialCard } from '@repo/graphql-types';
import { ZodTrialSearchSchema } from '@repo/zod-validations';
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
}

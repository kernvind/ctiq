import { Args, Int, Mutation, Resolver } from '@nestjs/graphql';
import { EligibilityMatchService } from './eligibility-match.service';
import {
  MatchResult,
  MatchedTrial,
  PatientProfileInput,
} from '@repo/graphql-types';
import { ZodNctIdSchema } from '@repo/zod-validations';
import { zodPipe } from '../common/pipes/zod-validation.pipe';

@Resolver()
export class EligibilityMatchResolver {
  constructor(private readonly service: EligibilityMatchService) {}

  /**
   * Stateless patient↔trial eligibility match (ROADMAP step 6). A mutation (not a query)
   * because it submits a patient profile and must not be response-cached. Returns null when
   * the trial has no extracted eligibility criteria yet. The profile is never persisted.
   */
  @Mutation(() => MatchResult, { nullable: true })
  async matchTrial(
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
    @Args('profile', { type: () => PatientProfileInput })
    profile: PatientProfileInput,
  ): Promise<MatchResult | null> {
    return this.service.matchTrial(nctId, profile);
  }

  /**
   * Patient-first: rank recruiting trials for a condition by eligibility fit (ROADMAP step
   * 6). A mutation because it submits a patient profile (must not be response-cached).
   * Drill into matchTrial(nctId, profile) for a trial's per-criterion verdicts.
   */
  @Mutation(() => [MatchedTrial])
  async matchTrials(
    @Args('condition', { type: () => String }) condition: string,
    @Args('profile', { type: () => PatientProfileInput })
    profile: PatientProfileInput,
    @Args('topK', { type: () => Int, nullable: true, defaultValue: 50 })
    topK: number,
    @Args('recruitingOnly', {
      type: () => Boolean,
      nullable: true,
      defaultValue: true,
    })
    recruitingOnly: boolean,
  ): Promise<MatchedTrial[]> {
    return this.service.matchTrials(condition, profile, topK, recruitingOnly);
  }
}

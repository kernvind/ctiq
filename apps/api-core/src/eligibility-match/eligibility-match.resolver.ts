import { Args, Int, Mutation, Resolver } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { Role } from '@repo/db';
import { EligibilityMatchService } from './eligibility-match.service';
import {
  MatchResult,
  MatchedTrial,
  PatientProfileInput,
} from '@repo/graphql-types';
import {
  ZodNctIdSchema,
  ZodConditionSchema,
  ZodPatientProfileSchema,
} from '@repo/zod-validations';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { RolesGuard } from '../auth/guards/roles.guard';
import { Roles } from '../auth/decorators/roles.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthedUser } from '../auth/decorators/current-user.decorator';
import { PortfolioService } from '../portfolio/portfolio.service';

/**
 * Eligibility matching is a clinician decision-support feature (Pro tier) — gated to the
 * CLINICIAN role. Auth guard runs first to attach the user, then RolesGuard enforces.
 */
@Resolver()
@UseGuards(GqlAuthGuard, RolesGuard)
@Roles(Role.CLINICIAN)
export class EligibilityMatchResolver {
  constructor(
    private readonly service: EligibilityMatchService,
    private readonly portfolio: PortfolioService,
  ) {}

  /**
   * Stateless patient↔trial eligibility match (ROADMAP step 6). A mutation (not a query)
   * because it submits a patient profile and must not be response-cached. Returns null when
   * the trial has no extracted eligibility criteria yet. The profile is never persisted.
   */
  @Mutation(() => MatchResult, { nullable: true })
  async matchTrial(
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
    @Args(
      'profile',
      { type: () => PatientProfileInput },
      zodPipe(ZodPatientProfileSchema),
    )
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
    @Args('condition', { type: () => String }, zodPipe(ZodConditionSchema))
    condition: string,
    @Args(
      'profile',
      { type: () => PatientProfileInput },
      zodPipe(ZodPatientProfileSchema),
    )
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

  /**
   * Portfolio screening (site-payer wedge): screen a patient profile against the current
   * user's open-trial portfolio (the trials their site is running) — not all of CT.gov. A
   * mutation because it submits a patient profile (must not be response-cached). Returns []
   * when the portfolio is empty. The profile is never persisted.
   */
  @Mutation(() => [MatchedTrial])
  async screenPortfolio(
    @CurrentUser() user: AuthedUser,
    @Args(
      'profile',
      { type: () => PatientProfileInput },
      zodPipe(ZodPatientProfileSchema),
    )
    profile: PatientProfileInput,
  ): Promise<MatchedTrial[]> {
    const nctIds = await this.portfolio.nctIdsForUser(user.id);
    return this.service.screenPortfolio(nctIds, profile);
  }
}

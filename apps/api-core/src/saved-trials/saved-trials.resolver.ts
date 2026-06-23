import { Resolver, Query, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { SavedTrial } from '@repo/graphql-types';
import { ZodNctIdSchema } from '@repo/zod-validations';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthedUser } from '../auth/decorators/current-user.decorator';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { SavedTrialsService } from './saved-trials.service';

@Resolver(() => SavedTrial)
export class SavedTrialsResolver {
  constructor(private readonly service: SavedTrialsService) {}

  @Query(() => [SavedTrial], { name: 'savedTrials' })
  @UseGuards(GqlAuthGuard)
  savedTrials(@CurrentUser() user: AuthedUser): Promise<SavedTrial[]> {
    return this.service.listForUser(user.id);
  }

  @Mutation(() => SavedTrial, { name: 'saveTrial' })
  @UseGuards(GqlAuthGuard)
  saveTrial(
    @CurrentUser() user: AuthedUser,
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
  ): Promise<SavedTrial> {
    return this.service.save(user.id, nctId.toUpperCase());
  }

  @Mutation(() => Boolean, { name: 'unsaveTrial' })
  @UseGuards(GqlAuthGuard)
  unsaveTrial(
    @CurrentUser() user: AuthedUser,
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
  ): Promise<boolean> {
    return this.service.remove(user.id, nctId.toUpperCase());
  }
}

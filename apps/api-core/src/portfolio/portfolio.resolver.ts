import { Resolver, Query, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { PortfolioTrial } from '@repo/graphql-types';
import { ZodNctIdSchema } from '@repo/zod-validations';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthedUser } from '../auth/decorators/current-user.decorator';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import { PortfolioService } from './portfolio.service';

@Resolver(() => PortfolioTrial)
export class PortfolioResolver {
  constructor(private readonly service: PortfolioService) {}

  @Query(() => [PortfolioTrial], { name: 'portfolio' })
  @UseGuards(GqlAuthGuard)
  portfolio(@CurrentUser() user: AuthedUser): Promise<PortfolioTrial[]> {
    return this.service.listForUser(user.id);
  }

  @Mutation(() => PortfolioTrial, { name: 'addPortfolioTrial' })
  @UseGuards(GqlAuthGuard)
  addPortfolioTrial(
    @CurrentUser() user: AuthedUser,
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
  ): Promise<PortfolioTrial> {
    return this.service.add(user.id, nctId.toUpperCase());
  }

  @Mutation(() => Boolean, { name: 'removePortfolioTrial' })
  @UseGuards(GqlAuthGuard)
  removePortfolioTrial(
    @CurrentUser() user: AuthedUser,
    @Args('nctId', { type: () => String }, zodPipe(ZodNctIdSchema))
    nctId: string,
  ): Promise<boolean> {
    return this.service.remove(user.id, nctId.toUpperCase());
  }
}

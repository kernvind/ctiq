import { Resolver, Query, Mutation, Args, ID } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { Landscape, CreateLandscapeInput } from '@repo/graphql-types';
import { ZodCreateLandscapeSchema } from '@repo/zod-validations';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthedUser } from '../auth/decorators/current-user.decorator';
import { zodPipe } from '../common/pipes/zod-validation.pipe';
import {
  LandscapesService,
  LandscapeRecord,
} from './landscapes.service';

/** Map a DB record (spec is JSON) to the typed GraphQL Landscape. */
function toLandscape(r: LandscapeRecord): Landscape {
  const spec = (r.spec ?? {}) as { q?: string; phase?: string | null };
  return {
    id: r.id,
    name: r.name,
    spec: { q: spec.q ?? '', phase: spec.phase ?? null },
    lastSeenNctIds: r.lastSeenNctIds ?? [],
    lastCheckedAt: r.lastCheckedAt ?? null,
    createdAt: r.createdAt,
  };
}

@Resolver(() => Landscape)
export class LandscapesResolver {
  constructor(private readonly service: LandscapesService) {}

  @Query(() => [Landscape], { name: 'landscapes' })
  @UseGuards(GqlAuthGuard)
  async landscapes(@CurrentUser() user: AuthedUser): Promise<Landscape[]> {
    const rows = await this.service.listForUser(user.id);
    return rows.map(toLandscape);
  }

  @Mutation(() => Landscape, { name: 'createLandscape' })
  @UseGuards(GqlAuthGuard)
  async createLandscape(
    @CurrentUser() user: AuthedUser,
    @Args('input', zodPipe(ZodCreateLandscapeSchema)) input: CreateLandscapeInput,
  ): Promise<Landscape> {
    const row = await this.service.create(user.id, {
      name: input.name,
      q: input.q,
      phase: input.phase,
    });
    return toLandscape(row);
  }

  @Mutation(() => Boolean, { name: 'deleteLandscape' })
  @UseGuards(GqlAuthGuard)
  deleteLandscape(
    @CurrentUser() user: AuthedUser,
    @Args('id', { type: () => ID }) id: string,
  ): Promise<boolean> {
    return this.service.remove(user.id, id);
  }

  @Mutation(() => Landscape, { name: 'markLandscapeSeen', nullable: true })
  @UseGuards(GqlAuthGuard)
  async markLandscapeSeen(
    @CurrentUser() user: AuthedUser,
    @Args('id', { type: () => ID }) id: string,
    @Args('nctIds', { type: () => [String] }) nctIds: string[],
  ): Promise<Landscape | null> {
    const row = await this.service.markSeen(user.id, id, nctIds);
    return row ? toLandscape(row) : null;
  }
}

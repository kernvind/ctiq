import { Resolver, Query } from '@nestjs/graphql';
import { UseGuards, UnauthorizedException } from '@nestjs/common';
import { User } from '@repo/graphql-types';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthedUser } from '../auth/decorators/current-user.decorator';
import { UsersService } from './users.service';

@Resolver(() => User)
export class UsersResolver {
  constructor(private readonly usersService: UsersService) {}

  /**
   * The current authenticated user. Guarded by the JWT — the token identifies who's
   * asking; we re-read from the DB so role/name reflect current state, not a stale token
   * claim. Throws if the token is valid but the user no longer exists.
   */
  @Query(() => User, { name: 'me' })
  @UseGuards(GqlAuthGuard)
  async me(@CurrentUser() user: AuthedUser): Promise<User> {
    const record = await this.usersService.findById(user.id);
    if (!record) throw new UnauthorizedException('User not found');
    return {
      id: record.id,
      email: record.email,
      name: record.name,
      // Prisma Role and the GraphQL UserRole share identical string values.
      role: record.role as unknown as User['role'],
    };
  }
}

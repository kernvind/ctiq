import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import { GqlExecutionContext } from '@nestjs/graphql';
import { Role } from '@repo/db';

/** Shape attached to `req.user` by JwtStrategy.validate after a valid access token. */
export interface AuthedUser {
  id: string;
  email: string;
  role: Role;
}

/**
 * Resolver param decorator that returns the authenticated user (set by the JWT auth
 * guard). Use on queries/mutations behind GqlAuthGuard; it reads `req.user` from the
 * GraphQL execution context.
 */
export const CurrentUser = createParamDecorator(
  (_data: unknown, context: ExecutionContext): AuthedUser => {
    const ctx = GqlExecutionContext.create(context);
    return ctx.getContext<{ req: { user: AuthedUser } }>().req.user;
  },
);

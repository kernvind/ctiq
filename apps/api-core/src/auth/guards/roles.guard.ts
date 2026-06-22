import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
  Logger,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { GqlExecutionContext } from '@nestjs/graphql';
import { Role } from '@repo/db';
import { ROLES_KEY } from '../decorators/roles.decorator';

interface RequestUser {
  id: string;
  email: string;
  role: Role;
}

/**
 * Enforces @Roles(...) on GraphQL resolvers. Reads the authenticated user (attached by
 * the auth guard via the JWT `role` claim) and checks it against the required roles.
 * Fails closed: missing user or insufficient role -> ForbiddenException.
 */
@Injectable()
export class RolesGuard implements CanActivate {
  private readonly logger = new Logger(RolesGuard.name);

  constructor(private readonly reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<Role[] | undefined>(
      ROLES_KEY,
      [context.getHandler(), context.getClass()],
    );

    // No @Roles metadata -> this guard imposes no restriction.
    if (!requiredRoles || requiredRoles.length === 0) {
      return true;
    }

    const gqlCtx = GqlExecutionContext.create(context);
    const req = gqlCtx.getContext<{ req?: { user?: RequestUser } }>().req;
    const user = req?.user;

    // Should be populated by an auth guard running first; fail closed if not.
    if (!user) {
      this.logger.warn(
        `RBAC denied: no authenticated user (required=[${requiredRoles.join(', ')}])`,
      );
      throw new ForbiddenException('Insufficient permissions');
    }

    if (!requiredRoles.includes(user.role)) {
      this.logger.warn(
        `RBAC denied: user id=${user.id} role=${user.role} ` +
          `required=[${requiredRoles.join(', ')}]`,
      );
      throw new ForbiddenException('Insufficient permissions');
    }

    this.logger.debug(
      `RBAC allowed: user id=${user.id} role=${user.role} ` +
        `required=[${requiredRoles.join(', ')}]`,
    );
    return true;
  }
}

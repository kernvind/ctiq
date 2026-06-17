import { SetMetadata } from '@nestjs/common';
import { Role } from '@repo/db';

export const ROLES_KEY = 'roles';

/**
 * Restrict a resolver/handler to the given role(s).
 *
 * Must be combined with an auth guard that populates `req.user` (which carries the
 * `role` claim from the JWT), and the RolesGuard, e.g.:
 *
 *   @UseGuards(GqlAuthGuard, RolesGuard)
 *   @Roles(Role.ADMIN)
 *   @Mutation(() => ...)
 *   adminOnlyThing() { ... }
 *
 * Order matters: GqlAuthGuard runs first to attach the user, then RolesGuard checks it.
 */
export const Roles = (...roles: Role[]) => SetMetadata(ROLES_KEY, roles);

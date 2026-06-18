import { ExecutionContext, ForbiddenException } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { GqlExecutionContext } from '@nestjs/graphql';
import { Role } from '@repo/db';
import { RolesGuard } from './roles.guard';

describe('RolesGuard', () => {
  let reflector: { getAllAndOverride: jest.Mock };
  let guard: RolesGuard;

  const context = {
    getHandler: () => null,
    getClass: () => null,
  } as unknown as ExecutionContext;

  function mockUser(user: unknown) {
    jest.spyOn(GqlExecutionContext, 'create').mockReturnValue({
      getContext: () => ({ req: { user } }),
    } as unknown as GqlExecutionContext);
  }

  beforeEach(() => {
    reflector = { getAllAndOverride: jest.fn() };
    guard = new RolesGuard(reflector as unknown as Reflector);
  });

  afterEach(() => jest.restoreAllMocks());

  it('allows when no @Roles metadata is present', () => {
    reflector.getAllAndOverride.mockReturnValue(undefined);
    expect(guard.canActivate(context)).toBe(true);
  });

  it('allows when the metadata is an empty roles array', () => {
    reflector.getAllAndOverride.mockReturnValue([]);
    expect(guard.canActivate(context)).toBe(true);
  });

  it('allows a user whose role is in the required set', () => {
    reflector.getAllAndOverride.mockReturnValue([Role.ADMIN, Role.ANALYST]);
    mockUser({ id: 'u1', username: 'a', role: Role.ANALYST });
    expect(guard.canActivate(context)).toBe(true);
  });

  it('denies (fails closed) a user whose role is not allowed', () => {
    reflector.getAllAndOverride.mockReturnValue([Role.ADMIN]);
    mockUser({ id: 'u1', username: 'a', role: Role.PATIENT });
    expect(() => guard.canActivate(context)).toThrow(ForbiddenException);
  });

  it('denies (fails closed) when there is no authenticated user', () => {
    reflector.getAllAndOverride.mockReturnValue([Role.ADMIN]);
    mockUser(undefined);
    expect(() => guard.canActivate(context)).toThrow(ForbiddenException);
  });
});

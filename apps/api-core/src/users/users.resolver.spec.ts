import { UnauthorizedException } from '@nestjs/common';
import { Role, UserStatus } from '@repo/db';
import { UsersResolver } from './users.resolver';
import { AuthedUser } from '../auth/decorators/current-user.decorator';

const authed: AuthedUser = {
  id: 'u1',
  email: 'alice@example.com',
  role: Role.CLINICIAN,
};

describe('UsersResolver', () => {
  let resolver: UsersResolver;
  let usersService: { findById: jest.Mock };

  beforeEach(() => {
    usersService = { findById: jest.fn() };
    resolver = new UsersResolver(usersService as never);
  });

  describe('me', () => {
    it('returns the current user re-read from the DB (not the token claims)', async () => {
      usersService.findById.mockResolvedValue({
        id: 'u1',
        email: 'alice@example.com',
        passwordHash: 'secret-hash',
        name: 'Alice',
        role: Role.ADMIN, // DB role differs from the token's CLINICIAN -> DB wins
        status: UserStatus.ACTIVE,
      });

      const result = await resolver.me(authed);

      expect(usersService.findById).toHaveBeenCalledWith('u1');
      expect(result).toEqual({
        id: 'u1',
        email: 'alice@example.com',
        name: 'Alice',
        role: Role.ADMIN,
      });
      // Sensitive fields are never returned.
      expect(result).not.toHaveProperty('passwordHash');
      expect(result).not.toHaveProperty('status');
    });

    it('throws Unauthorized when the token is valid but the user no longer exists', async () => {
      usersService.findById.mockResolvedValue(null);

      await expect(resolver.me(authed)).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
    });
  });
});

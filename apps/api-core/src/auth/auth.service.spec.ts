import { ConflictException, UnauthorizedException } from '@nestjs/common';
import { Role } from '@repo/db';
import { SignupRole } from '@repo/graphql-types';
import { AuthService } from './auth.service';

jest.mock('bcryptjs', () => ({ compare: jest.fn(), hash: jest.fn() }));
import { compare, hash } from 'bcryptjs';
const compareMock = compare as jest.Mock;
const hashMock = hash as jest.Mock;

const user = {
  id: 'u1',
  email: 'alice@example.com',
  passwordHash: 'stored-hash',
  name: null,
  role: Role.CLINICIAN,
  status: 'ACTIVE',
};

describe('AuthService', () => {
  let usersService: {
    findByEmail: jest.Mock;
    findById: jest.Mock;
    create: jest.Mock;
  };
  let jwtService: { sign: jest.Mock };
  let sessionService: {
    issue: jest.Mock;
    rotate: jest.Mock;
    revoke: jest.Mock;
  };
  let service: AuthService;

  beforeEach(() => {
    jest.clearAllMocks();
    usersService = {
      findByEmail: jest.fn(),
      findById: jest.fn(),
      create: jest.fn(),
    };
    jwtService = { sign: jest.fn().mockReturnValue('signed.jwt') };
    sessionService = {
      issue: jest.fn().mockResolvedValue('refresh-raw'),
      rotate: jest.fn(),
      revoke: jest.fn().mockResolvedValue(undefined),
    };
    service = new AuthService(
      usersService as never,
      jwtService as never,
      sessionService as never,
    );
  });

  describe('login', () => {
    it('returns access + refresh tokens with the role claim on success', async () => {
      usersService.findByEmail.mockResolvedValue(user);
      compareMock.mockResolvedValue(true);

      const result = await service.login(
        { email: 'alice@example.com', password: 'pw' },
        { ip: '1.1.1.1' },
      );

      expect(jwtService.sign).toHaveBeenCalledWith({
        sub: 'u1',
        email: 'alice@example.com',
        role: Role.CLINICIAN,
      });
      expect(sessionService.issue).toHaveBeenCalledWith('u1', {
        ip: '1.1.1.1',
      });
      expect(result).toEqual({
        accessToken: 'signed.jwt',
        refreshToken: 'refresh-raw',
      });
    });

    it('rejects an unknown user and never issues a session', async () => {
      usersService.findByEmail.mockResolvedValue(null);

      await expect(
        service.login({ email: 'ghost@example.com', password: 'pw' }),
      ).rejects.toBeInstanceOf(UnauthorizedException);
      expect(sessionService.issue).not.toHaveBeenCalled();
    });

    it('rejects a wrong password', async () => {
      usersService.findByEmail.mockResolvedValue(user);
      compareMock.mockResolvedValue(false);

      await expect(
        service.login({ email: 'alice@example.com', password: 'bad' }),
      ).rejects.toBeInstanceOf(UnauthorizedException);
      expect(sessionService.issue).not.toHaveBeenCalled();
    });
  });

  describe('signup', () => {
    const dto = {
      email: 'bob@example.com',
      password: 'password123',
      name: 'Bob',
      role: SignupRole.PATIENT,
    };

    it('creates the user with the mapped role and returns tokens', async () => {
      usersService.findByEmail.mockResolvedValue(null);
      hashMock.mockResolvedValue('new-hash');
      usersService.create.mockResolvedValue({
        ...user,
        id: 'u2',
        role: Role.PATIENT,
      });

      const result = await service.signup(dto);

      expect(usersService.create).toHaveBeenCalledWith(
        'bob@example.com',
        'new-hash',
        'Bob',
        Role.PATIENT, // SignupRole.PATIENT mapped to Prisma Role
      );
      expect(sessionService.issue).toHaveBeenCalledWith('u2', {});
      expect(result).toEqual({
        accessToken: 'signed.jwt',
        refreshToken: 'refresh-raw',
      });
    });

    it('rejects a taken email', async () => {
      usersService.findByEmail.mockResolvedValue(user);

      await expect(service.signup(dto)).rejects.toBeInstanceOf(
        ConflictException,
      );
      expect(usersService.create).not.toHaveBeenCalled();
    });
  });

  describe('refresh', () => {
    it('rotates the token and mints a new access token for the owner', async () => {
      sessionService.rotate.mockResolvedValue({
        userId: 'u1',
        refreshToken: 'new-refresh',
      });
      usersService.findById.mockResolvedValue(user);

      const result = await service.refresh('old-refresh', {});

      expect(sessionService.rotate).toHaveBeenCalledWith('old-refresh', {});
      expect(jwtService.sign).toHaveBeenCalledWith({
        sub: 'u1',
        email: 'alice@example.com',
        role: Role.CLINICIAN,
      });
      expect(result).toEqual({
        accessToken: 'signed.jwt',
        refreshToken: 'new-refresh',
      });
    });

    it('rejects if the session owner no longer exists', async () => {
      sessionService.rotate.mockResolvedValue({
        userId: 'gone',
        refreshToken: 'new-refresh',
      });
      usersService.findById.mockResolvedValue(null);

      await expect(service.refresh('old-refresh')).rejects.toBeInstanceOf(
        UnauthorizedException,
      );
    });
  });

  describe('logout', () => {
    it('revokes the session for the token and returns true', async () => {
      const result = await service.logout('some-refresh');
      expect(sessionService.revoke).toHaveBeenCalledWith('some-refresh');
      expect(result).toBe(true);
    });
  });
});

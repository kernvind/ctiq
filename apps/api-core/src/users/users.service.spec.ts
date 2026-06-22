import { Role, UserStatus } from '@repo/db';
import { PrismaService } from '../prisma/prisma.service';
import { UsersService } from './users.service';

describe('UsersService', () => {
  let service: UsersService;
  let user: { findUnique: jest.Mock; create: jest.Mock };
  let prisma: PrismaService;

  const record = {
    id: 'u1',
    email: 'alice@example.com',
    passwordHash: 'hash',
    name: null,
    role: Role.PATIENT,
    status: UserStatus.ACTIVE,
  };

  beforeEach(() => {
    user = { findUnique: jest.fn(), create: jest.fn() };
    prisma = { client: { user } } as unknown as PrismaService;
    service = new UsersService(prisma);
  });

  describe('findByEmail', () => {
    it('looks a user up by their unique email and returns the record', async () => {
      user.findUnique.mockResolvedValue(record);

      const res = await service.findByEmail('alice@example.com');

      expect(user.findUnique).toHaveBeenCalledWith({
        where: { email: 'alice@example.com' },
      });
      expect(res).toBe(record);
    });

    it('returns null when no user matches the email', async () => {
      user.findUnique.mockResolvedValue(null);

      expect(await service.findByEmail('ghost@example.com')).toBeNull();
    });
  });

  describe('findById', () => {
    it('looks a user up by id', async () => {
      user.findUnique.mockResolvedValue(record);

      const res = await service.findById('u1');

      expect(user.findUnique).toHaveBeenCalledWith({ where: { id: 'u1' } });
      expect(res).toBe(record);
    });

    it('returns null when the id is unknown', async () => {
      user.findUnique.mockResolvedValue(null);

      expect(await service.findById('nope')).toBeNull();
    });
  });

  describe('create', () => {
    it('persists the given fields with an explicit role', async () => {
      user.create.mockResolvedValue(record);

      const res = await service.create(
        'alice@example.com',
        'hash',
        'Alice',
        Role.CLINICIAN,
      );

      expect(user.create).toHaveBeenCalledWith({
        data: {
          email: 'alice@example.com',
          passwordHash: 'hash',
          name: 'Alice',
          role: Role.CLINICIAN,
        },
      });
      expect(res).toBe(record);
    });

    it('omits name/role when not supplied so Prisma applies the schema default', async () => {
      user.create.mockResolvedValue(record);

      await service.create('bob@example.com', 'hash');

      expect(user.create).toHaveBeenCalledWith({
        data: {
          email: 'bob@example.com',
          passwordHash: 'hash',
          name: undefined,
          role: undefined,
        },
      });
    });
  });
});

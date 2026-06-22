import { Injectable } from '@nestjs/common';
import { Role, UserStatus } from '@repo/db';
import { PrismaService } from '../prisma/prisma.service';

export interface UserRecord {
  id: string;
  email: string;
  passwordHash: string;
  name: string | null;
  role: Role;
  status: UserStatus;
}

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async findByEmail(email: string): Promise<UserRecord | null> {
    return await this.prisma.client.user.findUnique({
      where: { email },
    });
  }
  async findById(id: string): Promise<UserRecord | null> {
    return await this.prisma.client.user.findUnique({
      where: { id },
    });
  }
  async create(
    email: string,
    passwordHash: string,
    name?: string,
    role?: Role,
  ): Promise<UserRecord> {
    // role omitted -> Prisma applies the schema default (PATIENT).
    return await this.prisma.client.user.create({
      data: { email, passwordHash, name, role },
    });
  }
}

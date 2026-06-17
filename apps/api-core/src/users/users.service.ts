import { Injectable } from '@nestjs/common';
import { Role, UserStatus } from '@repo/db';
import { PrismaService } from '../prisma/prisma.service';

export interface UserRecord {
  id: string;
  email: string;
  username: string;
  passwordHash: string;
  name: string | null;
  role: Role;
  status: UserStatus;
}

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async findByUsername(username: string): Promise<UserRecord | null> {
    return await this.prisma.client.user.findUnique({
      where: { username },
    });
  }
  async findByEmail(email: string): Promise<UserRecord | null> {
    return await this.prisma.client.user.findUnique({
      where: { email },
    });
  }
  async create(
    username: string,
    email: string,
    passwordHash: string,
    name?: string,
  ): Promise<UserRecord> {
    return await this.prisma.client.user.create({
      data: { username, email, passwordHash, name },
    });
  }
}

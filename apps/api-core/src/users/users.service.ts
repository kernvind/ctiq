import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

export interface UserRecord {
  id: number;
  email: string;
  username: string;
  passwordHash: string;
  name: string | null;
}

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async findByUsername(username: string): Promise<UserRecord | null> {
    return this.prisma.client.user.findUnique({ where: { username } });
  }

  async create(
    username: string,
    email: string,
    passwordHash: string,
    name?: string,
  ): Promise<UserRecord> {
    return this.prisma.client.user.create({
      data: { username, email, passwordHash, name },
    });
  }
}

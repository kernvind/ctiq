import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { getPrismaClient, PrismaClient } from '@repo/db';

@Injectable()
export class PrismaService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);
  private prismaClient: PrismaClient;

  constructor(private readonly configService: ConfigService) {}

  async onModuleInit() {
    const connectionString =
      this.configService.getOrThrow<string>('DATABASE_URL');

    this.prismaClient = getPrismaClient(connectionString) as PrismaClient;
    await this.prismaClient.$connect();
    this.logger.log('Prisma connected');
  }

  async onModuleDestroy() {
    await this.prismaClient?.$disconnect();
    this.logger.log('Prisma disconnected');
  }

  get client(): PrismaClient {
    if (!this.prismaClient) {
      throw new Error('PrismaService not initialized yet');
    }
    return this.prismaClient;
  }
}

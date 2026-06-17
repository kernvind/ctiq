import { Injectable } from '@nestjs/common';
import { PrismaService } from './prisma/prisma.service';
@Injectable()
export class AppService {
  constructor(private readonly prisma: PrismaService) {}

  async getHello(): Promise<string> {
    // Liveness check: verify DB connectivity without reading any table data.
    await this.prisma.client.$queryRaw`SELECT 1`;
    return 'ok';
  }
}

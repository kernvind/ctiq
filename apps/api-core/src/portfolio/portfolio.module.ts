import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { PortfolioService } from './portfolio.service';
import { PortfolioResolver } from './portfolio.resolver';

@Module({
  imports: [PrismaModule],
  providers: [PortfolioService, PortfolioResolver],
  // Exported so the eligibility-match module can read a user's portfolio NCT ids for screening.
  exports: [PortfolioService],
})
export class PortfolioModule {}

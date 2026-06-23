import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { LandscapesService } from './landscapes.service';
import { LandscapesResolver } from './landscapes.resolver';

@Module({
  imports: [PrismaModule],
  providers: [LandscapesService, LandscapesResolver],
})
export class LandscapesModule {}

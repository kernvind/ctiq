import { Module } from '@nestjs/common';
import { PrismaModule } from '../prisma/prisma.module';
import { SavedTrialsService } from './saved-trials.service';
import { SavedTrialsResolver } from './saved-trials.resolver';

@Module({
  imports: [PrismaModule],
  providers: [SavedTrialsService, SavedTrialsResolver],
})
export class SavedTrialsModule {}

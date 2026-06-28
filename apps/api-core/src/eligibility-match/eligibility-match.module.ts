import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { EligibilityMatchService } from './eligibility-match.service';
import { EligibilityMatchResolver } from './eligibility-match.resolver';

@Module({
  imports: [
    HttpModule.registerAsync({
      useFactory: (config: ConfigService) => ({
        baseURL: config.getOrThrow<string>('SEARCH_API_URL'),
        timeout: 10_000,
        headers: {
          'X-Internal-Token': config.getOrThrow<string>('SEARCH_API_TOKEN'),
        },
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [EligibilityMatchService, EligibilityMatchResolver],
  exports: [EligibilityMatchService],
})
export class EligibilityMatchModule {}

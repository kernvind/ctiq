import { join } from 'node:path';
import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { HttpModule } from '@nestjs/axios';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { LoggerModule } from 'nestjs-pino';

import { buildLoggerParams } from './common/logging/logger.params';
import { formatGraphQLError } from './common/graphql/format-error';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { TrialSearchModule } from './trial-search/trial-search.module';
import { EligibilityMatchModule } from './eligibility-match/eligibility-match.module';
import { SavedTrialsModule } from './saved-trials/saved-trials.module';
import { LandscapesModule } from './landscapes/landscapes.module';
import { HealthResolver } from './health/health.resolver';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { APP_FILTER } from '@nestjs/core';
import { GlobalExceptionFilter } from './common/filters/global-exception.filter';
@Module({
  imports: [
    // 1. Initialize global configuration management first
    ConfigModule.forRoot({
      isGlobal: true,
    }),

    // Structured logging (Pino) — JSON to stdout in prod (ingested by Cloud
    // Logging on GKE), pretty output in dev. Provides per-request logs + req id.
    LoggerModule.forRoot(buildLoggerParams()),

    // 2. Safely bootstrap HttpModule using the global ConfigService
    HttpModule.registerAsync({
      useFactory: (configService: ConfigService) => ({
        timeout: configService.get<number>('HTTP_TIMEOUT', 5000),
      }),
      inject: [ConfigService],
    }),

    // 3. Database module resolves next using lazy imports internally
    PrismaModule,

    AuthModule,
    TrialSearchModule,
    EligibilityMatchModule,
    SavedTrialsModule,
    LandscapesModule,

    // 4. GraphQL gateway setup
    GraphQLModule.forRoot<ApolloDriverConfig>({
      driver: ApolloDriver,
      autoSchemaFile: join(process.cwd(), 'schema.gql'),
      sortSchema: true,
      // Never leak stack traces or internal error detail to the client — covers
      // Apollo-layer errors (validation/serialization) that bypass the resolver
      // and GlobalExceptionFilter. See common/graphql/format-error.ts.
      includeStacktraceInErrorResponses: false,
      formatError: formatGraphQLError,
    }),
  ],
  controllers: [AppController],
  providers: [
    AppService,
    HealthResolver,
    {
      provide: APP_FILTER,
      useClass: GlobalExceptionFilter,
    },
  ],
})
export class AppModule {}

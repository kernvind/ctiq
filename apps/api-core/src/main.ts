import { randomUUID } from 'node:crypto';
import { NestFactory } from '@nestjs/core';
import {
  FastifyAdapter,
  NestFastifyApplication,
} from '@nestjs/platform-fastify';
import { Logger } from 'nestjs-pino';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create<NestFastifyApplication>(
    AppModule,
    // Correlation id per request: reuse an inbound `x-request-id` if present,
    // else mint a UUID. Fastify assigns req.id before Pino logs, so this is set
    // here (not in the Pino config) to flow into every request log.
    new FastifyAdapter({
      requestIdHeader: 'x-request-id',
      genReqId: () => randomUUID(),
    }),
    // Buffer logs until the Pino logger is resolved so startup logs use it too.
    { bufferLogs: true },
  );
  // Route Nest's logger (and every `new Logger(...)` instance) through Pino.
  app.useLogger(app.get(Logger));
  await app.listen(process.env.PORT ?? 3001, '0.0.0.0');
}
bootstrap();

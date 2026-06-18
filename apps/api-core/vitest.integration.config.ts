import { defineConfig } from 'vitest/config';
import swc from 'unplugin-swc';

// Integration tests run on Vitest (not Jest) because they pull in modern ESM-only deps
// (Testcontainers -> archiver) and the Prisma 7 client's runtime dynamic import(), both
// of which Vitest handles natively. Unit tests stay on Jest.
//
// The swc plugin is required for the app-boot e2e: NestJS DI relies on
// emitDecoratorMetadata, which esbuild (Vitest's default) does not emit but swc does.
export default defineConfig({
  test: {
    include: ['test/**/*.int-spec.ts'],
    testTimeout: 180_000,
    hookTimeout: 180_000,
    environment: 'node',
    pool: 'forks',
    fileParallelism: false,
    // Force production logging: in dev mode the app's pino logger spawns a pino-pretty
    // transport worker thread, which is flaky inside Vitest's forked worker (crashes CI
    // with "Worker exited unexpectedly"). Production mode emits plain JSON, no transport.
    // Set here so it's in effect before AppModule (and its LoggerModule) is imported.
    env: { NODE_ENV: 'production' },
  },
  plugins: [
    swc.vite({
      jsc: {
        target: 'es2022',
        parser: { syntax: 'typescript', decorators: true },
        transform: { legacyDecorator: true, decoratorMetadata: true },
      },
    }),
  ],
});

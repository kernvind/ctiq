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

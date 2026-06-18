import { defineConfig } from 'vitest/config';
import path from 'node:path';

// Unit tests for server-side web logic (server actions + lib helpers). Node environment
// — no DOM needed. Next/server modules are mocked in the specs.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['lib/**/*.test.ts', 'app/**/*.test.ts'],
  },
  resolve: {
    // Mirror the tsconfig "@/*": "./*" alias.
    alias: { '@': path.resolve(__dirname, '.') },
  },
});

import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",

  // Tells Next.js where the monorepo root is so the standalone file tracer
  // can follow imports into packages/* and include them in the output.
  outputFileTracingRoot: path.join(__dirname, "../../"),

  // @repo/ui ships TypeScript source (no pre-compiled dist) — Next.js must
  // transpile it directly rather than trying to import compiled JS.
  transpilePackages: ["@repo/ui"],

  // pino is a Node-only logger (lib/logger.ts) — keep it external so Next loads it
  // as a real module instead of bundling it (recommended by pino under standalone).
  serverExternalPackages: ["pino"],
};

export default nextConfig;

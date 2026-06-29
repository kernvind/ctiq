import pino from "pino";

/**
 * Server-only structured logger for the dashboard's server actions / route handlers.
 *
 * Mirrors api-core's pino config (apps/api-core/src/common/logging/logger.params.ts) so every
 * service emits ONE JSON shape to stdout — ingested by Cloud Logging via the `severity` field.
 * No log files, and no `pino-pretty` transport: the transport spins up a worker thread, which
 * is fragile under Next's `output: "standalone"` tracer — plain JSON is the robust choice here.
 *
 * Do NOT import this into a Client Component. It's Node-only (pino can't run in the browser)
 * and is marked external in next.config.ts. Use it only from `"use server"` files.
 *
 * PHI/secret hygiene: never pass a patient `profile`, match `verdicts`, passwords, or tokens.
 * The redact paths below are belt-and-suspenders — the real rule is don't log those payloads.
 */

// Pino level label → Google Cloud Logging severity (matches api-core).
const PINO_LEVEL_TO_GCP_SEVERITY: Record<string, string> = {
  trace: "DEBUG",
  debug: "DEBUG",
  info: "INFO",
  warn: "WARNING",
  error: "ERROR",
  fatal: "CRITICAL",
};

// Fields that must never reach logs (secrets / future PHI).
const REDACT_PATHS = [
  "*.password",
  "*.passwordHash",
  "*.token",
  "profile",
  "*.profile",
];

const isProd = process.env.NODE_ENV === "production";

export const logger = pino({
  level: process.env.LOG_LEVEL ?? (isProd ? "info" : "debug"),
  messageKey: "message",
  redact: { paths: REDACT_PATHS, censor: "[REDACTED]" },
  formatters: {
    level(label) {
      return {
        severity: PINO_LEVEL_TO_GCP_SEVERITY[label] ?? "DEFAULT",
        level: label,
      };
    },
  },
  timestamp: () => `,"time":"${new Date().toISOString()}"`,
});

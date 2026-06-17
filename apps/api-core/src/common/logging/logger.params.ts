import type { Params } from 'nestjs-pino';

// Pino level label -> Google Cloud Logging severity. On GKE, container stdout is
// ingested by Cloud Logging, which reads the `severity` field.
// https://cloud.google.com/logging/docs/reference/v2/rest/v2/LogEntry#LogSeverity
const PINO_LEVEL_TO_GCP_SEVERITY: Record<string, string> = {
  trace: 'DEBUG',
  debug: 'DEBUG',
  info: 'INFO',
  warn: 'WARNING',
  error: 'ERROR',
  fatal: 'CRITICAL',
};

// Fields that must never be written to logs (secrets / future PHI).
const REDACT_PATHS = [
  'req.headers.authorization',
  'req.headers.cookie',
  'req.body.password',
  'req.body.variables.input.password',
  'req.body.input.password',
  '*.password',
  '*.passwordHash',
  '*.token',
];

export function buildLoggerParams(): Params {
  const isProd = process.env.NODE_ENV === 'production';
  const level = process.env.LOG_LEVEL ?? (isProd ? 'info' : 'debug');

  return {
    pinoHttp: {
      level,
      // req.id (correlation id) is assigned by the Fastify adapter in main.ts.
      redact: { paths: REDACT_PATHS, censor: '[REDACTED]' },
      // Structured JSON to stdout in prod (for Cloud Logging); pretty, human-
      // readable output in local dev.
      ...(isProd
        ? {
            messageKey: 'message',
            formatters: {
              level(label: string) {
                return {
                  severity: PINO_LEVEL_TO_GCP_SEVERITY[label] ?? 'DEFAULT',
                  level: label,
                };
              },
            },
            timestamp: () => `,"time":"${new Date().toISOString()}"`,
          }
        : {
            transport: {
              target: 'pino-pretty',
              options: { singleLine: true, translateTime: 'SYS:standard' },
            },
          }),
    },
  };
}

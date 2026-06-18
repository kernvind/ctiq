import { Logger } from '@nestjs/common';

// Silence Nest's structured logs during tests so CI output stays readable.
// (Logging behavior is asserted explicitly where it matters; this only suppresses
// the incidental log lines emitted by services under test.)
Logger.overrideLogger(false);

import { PrismaClient } from "./generated/prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export function getPrismaClient(connectionString: string): PrismaClient {
  if (globalForPrisma.prisma) {
    return globalForPrisma.prisma;
  }
  const url = connectionString || process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error(
      "[db] connectionString is required to initialize Prisma client.",
    );
  }

  const client = new PrismaClient({
    adapter: new PrismaPg({ connectionString }),
  });

  globalForPrisma.prisma = client;

  return client;
}

/**
 * Always create a fresh, non-cached Prisma client for a specific connection string.
 * Unlike getPrismaClient (a process-wide singleton), this is for tests and any caller
 * that needs an isolated client (e.g. an ephemeral test database).
 */
export function createPrismaClient(connectionString: string): PrismaClient {
  return new PrismaClient({
    adapter: new PrismaPg({ connectionString }),
  });
}

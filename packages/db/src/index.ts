export { getPrismaClient } from "./client"; // exports instance of prisma
export * from "./generated/prisma/client"; // exports generated types from prisma
export {
  PrismaClientKnownRequestError,
  PrismaClientValidationError,
  PrismaClientInitializationError,
  PrismaClientRustPanicError,
} from "@prisma/client/runtime/client"; // re-exporting for easier imports in other modules

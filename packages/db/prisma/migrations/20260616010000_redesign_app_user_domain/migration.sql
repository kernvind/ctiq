-- Redesign the user/auth domain in the `app` schema.
--
-- The previous `User`/`Post` tables were throwaway test scaffolding. `Post` is removed
-- entirely and `User` is rebuilt with a cuid() string PK, role/status enums, and
-- account-lifecycle timestamps, plus a `Session` table for refresh-token revocation.
-- This drops the old test rows by design (the PK type changes int -> text).

-- Drop scaffold + old test tables (Post first to remove its FK to User).
DROP TABLE "app"."Post";
DROP TABLE "app"."User";

-- CreateEnum
CREATE TYPE "app"."Role" AS ENUM ('PATIENT', 'CLINICIAN', 'ANALYST', 'ADMIN');

-- CreateEnum
CREATE TYPE "app"."UserStatus" AS ENUM ('ACTIVE', 'SUSPENDED', 'DELETED');

-- CreateTable
CREATE TABLE "app"."User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "username" TEXT NOT NULL,
    "passwordHash" TEXT NOT NULL,
    "name" TEXT,
    "role" "app"."Role" NOT NULL DEFAULT 'PATIENT',
    "status" "app"."UserStatus" NOT NULL DEFAULT 'ACTIVE',
    "emailVerifiedAt" TIMESTAMP(3),
    "lastLoginAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "app"."Session" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "tokenHash" TEXT NOT NULL,
    "userAgent" TEXT,
    "ip" TEXT,
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "revokedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Session_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_email_key" ON "app"."User"("email");

-- CreateIndex
CREATE UNIQUE INDEX "User_username_key" ON "app"."User"("username");

-- CreateIndex
CREATE UNIQUE INDEX "Session_tokenHash_key" ON "app"."Session"("tokenHash");

-- CreateIndex
CREATE INDEX "Session_userId_idx" ON "app"."Session"("userId");

-- AddForeignKey
ALTER TABLE "app"."Session" ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES "app"."User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

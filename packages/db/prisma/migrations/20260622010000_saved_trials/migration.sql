-- Watchlist: a user's saved trials.
--
-- `nctId` is a by-ID reference into the clinical-trial domain (ctiq-db, separate schema),
-- deliberately NOT a cross-ORM foreign key. The unique (userId, nctId) makes saving the
-- same trial idempotent.

-- CreateTable
CREATE TABLE "app"."SavedTrial" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "nctId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SavedTrial_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "SavedTrial_userId_idx" ON "app"."SavedTrial"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "SavedTrial_userId_nctId_key" ON "app"."SavedTrial"("userId", "nctId");

-- AddForeignKey
ALTER TABLE "app"."SavedTrial" ADD CONSTRAINT "SavedTrial_userId_fkey" FOREIGN KEY ("userId") REFERENCES "app"."User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

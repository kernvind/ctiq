-- Open-trial portfolio: the trials a site is actively running and wants to enroll into
-- (site-payer wedge). Same shape as SavedTrial but semantically distinct.
--
-- `nctId` is a by-ID reference into the clinical-trial domain (ctiq-db, separate schema),
-- deliberately NOT a cross-ORM foreign key. The unique (userId, nctId) makes adding the
-- same trial idempotent.

-- CreateTable
CREATE TABLE "app"."PortfolioTrial" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "nctId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "PortfolioTrial_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "PortfolioTrial_userId_idx" ON "app"."PortfolioTrial"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "PortfolioTrial_userId_nctId_key" ON "app"."PortfolioTrial"("userId", "nctId");

-- AddForeignKey
ALTER TABLE "app"."PortfolioTrial" ADD CONSTRAINT "PortfolioTrial_userId_fkey" FOREIGN KEY ("userId") REFERENCES "app"."User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

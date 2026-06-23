-- Saved landscapes: a named, re-runnable query an analyst monitors for new trials.
--
-- `spec` is an agent-ready JSON query (v1 wraps the semantic search). `lastSeenNctIds` +
-- `lastCheckedAt` back the on-view "new since last check" monitoring delta.

-- CreateTable
CREATE TABLE "app"."Landscape" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "spec" JSONB NOT NULL,
    "lastSeenNctIds" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "lastCheckedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Landscape_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Landscape_userId_idx" ON "app"."Landscape"("userId");

-- AddForeignKey
ALTER TABLE "app"."Landscape" ADD CONSTRAINT "Landscape_userId_fkey" FOREIGN KEY ("userId") REFERENCES "app"."User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

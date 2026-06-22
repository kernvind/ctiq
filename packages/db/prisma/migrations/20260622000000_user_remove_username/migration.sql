-- Remove the `username` column from the user/auth domain.
--
-- Login now authenticates by email (the sole unique human identifier); username was
-- redundant. Drop its unique index first, then the column. Existing rows keep their
-- email/password — only the username value is discarded.

-- DropIndex
DROP INDEX "app"."User_username_key";

-- AlterTable
ALTER TABLE "app"."User" DROP COLUMN "username";

-- Move the user/auth domain into a dedicated `app` schema (two-ORM domain split).
-- The clinical-trial domain is owned by the Python ctiq-db package in schema `trials`
-- and is intentionally not referenced here.
--
-- ALTER TABLE ... SET SCHEMA is a metadata-only change in PostgreSQL: rows, indexes,
-- primary keys, and the User<->Post foreign key all move with the tables. No data is
-- rewritten.

-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "app";

-- Move existing tables from public into app
ALTER TABLE "public"."User" SET SCHEMA "app";
ALTER TABLE "public"."Post" SET SCHEMA "app";

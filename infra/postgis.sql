CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;
-- P0 persistence probes are private, never exposed through PostgREST.
CREATE SCHEMA IF NOT EXISTS geoai_internal;
REVOKE ALL ON SCHEMA geoai_internal FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS geoai_internal.persistence_probe (id text PRIMARY KEY, value text NOT NULL);
ALTER TABLE geoai_internal.persistence_probe ENABLE ROW LEVEL SECURITY;

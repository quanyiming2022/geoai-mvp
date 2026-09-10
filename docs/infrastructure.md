# P0 infrastructure
Upstream: https://github.com/supabase/supabase
Tag: self-hosted/v0.8.1
Exact commit: 8c7a4d9dbbaf8b552893822e89d7bf06f33f9220
Retrieval date: 2026-09-11
Tag object 690080884040e238926ba22606e8c05a3536829b resolves to the commit above.
`upstream.lock.json` records the selected official Docker files and SHA256 hashes.
Official files remain unchanged. Only `infra/docker-compose.geoai.yml` customizes services.
Compose relative paths resolve from the FIRST file (infra/supabase/upstream).

One database: Supabase `db` (PostgreSQL 17); enable PostGIS in extensions schema.
No standalone postgres/postgis container. Supavisor is an optional `pooler` profile;
local API uses db directly. Database host port is separate from its container port.
P0 creates only a private persistence probe table with RLS; business tables and
owner/member/role RLS belong to P1 and have not been implemented or verified.

Storage: Supabase Storage v1.74.0, file backend, shared named volume with imgproxy.
License checked at https://github.com/supabase/storage/blob/v1.74.0/LICENSE (Apache-2.0),
copy in docs/licenses. No additional MinIO or S3 server. ObjectStorageProvider
encapsulates REST details and supports future S3 implementations. Uploads can stream;
P0 byte-returning get_object is only for small probes; large raster consumers must
use signed URLs/window reads in P3/P4. Redis 7.2 line uses BSD-3-Clause;
third-party distribution obligations still need a full audit before commercial delivery.
ResearchSkySensePPAdapter remains disabled/research_only; mock is not a real inference model.

Named volumes geoai-db, geoai-storage, geoai-redis persist restarts and container recreation.
Upstream db-config persists database encryption material. Redis enables AOF every second.
Never run `down -v` against valuable data. Restart tests are NOT backup/restore tests.
Keep encrypted database backups and a coordinated object-volume backup before production.
All published GeoAI ports bind to 127.0.0.1. Optional pooler profile uses upstream port defaults;
review its port bindings before enabling it on a shared host.

Upstream changes reviewed: Envoy replaces Kong; API_EXTERNAL_URL includes /auth/v1;
PG17 replaces PG15; Analytics/Vector are opt-in. No cloud account or GPU required.

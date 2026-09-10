# P0 implementation plan
Goal: reproducible local infrastructure, without P1 business features.
Architecture: Next.js status shell → FastAPI → replaceable storage/compute/model interfaces.
Official pinned Supabase provides the only PostgreSQL, Auth, REST, Realtime and file Storage.
GeoAI override adds Redis, API and raster worker; named volumes persist data.

- [x] Inspect correct empty repository and macOS arm64 / Docker.
- [x] Install user-level Node 24.21.0; verify npm and pnpm 12.3.4.
- [x] Vendor upstream with commit and byte integrity manifest.
- [x] Write contract tests; implement storage error handling and mock adapter/compute.
- [x] Add FastAPI health/readiness and repository interfaces, raster heartbeat.
- [x] Add Compose override, PostGIS init SQL and local secret generation.
- [x] Add Next.js P0 status shell, exact package versions and lockfiles.
- [x] Run build/typecheck/lint/unit tests locally.
- [x] Run actual Compose, Auth, REST, WebSocket, Storage, SQL, Redis tests.
- [x] Create persistence probe, restart services, verify database/object/Redis data.
- [x] Verify browser and record evidence.
Git delivery: commit and push feat/geoai-mvp after passing all local acceptance checks.

Tests: storage roundtrip/absence/error propagation, signed URLs, mock determinism,
research rejection and readiness dependency failures. Live tests must fail rather than
skip when required infrastructure is unavailable. No business RLS claim in P0;
P1 introduces spatial business migrations and user isolation tests.

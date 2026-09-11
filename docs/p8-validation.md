# Local P8 acceptance — 2026-09-11

Environment: /Users/quanyiming/Projects/geoai-mvp, macOS arm64, Node 24.21.0, pnpm 12.3.4. Branch feat/geoai-mvp. GitHub is code hosting only.

- Next.js production build, typecheck, ESLint and 3 frontend tests: PASS.
- Backend 43 tests and Ruff: PASS. Includes geospatial grid, bounded crops, rotated footprint, failed write compensation, process startup failure, cancellation fencing.
- P8 real integration: new accounts/project/upload -> COG -> Visual Prompt support image/mask -> AOI -> durable job -> MockComputeProvider/MockAdapter -> PostGIS polygon -> reject -> accept -> Next GeoJSON download: PASS.
- Caller SQL RLS, outsider API denial, viewer read-only, immutable original geometry, two audit records with correct reviewer: PASS.
- Historical results remain accessible by job; task pagination: PASS.
- P7 concurrent idempotency, direct SQL transition denial, lock timeout, cancellation/late write protection, Redis restart and Worker recovery: PASS.
- P4 regression after Worker supervision changes: COG, thumbnail, Range 206, CRS/PostGIS footprint, retry, tiles and Next proxy: PASS.
- Full infrastructure acceptance after P8: 14 healthy containers, PostgreSQL/PostGIS, Redis, Auth/PostgREST/Realtime, Storage CRUD/signed URLs, real DB/Storage/Redis restart persistence, API/Web health: PASS.
- Supabase security advisors: no issues. Upstream pinned 25-file integrity: PASS.
- Browser: raster visible, AOI rectangle saved, layer visibility/opacity changed, Visual Prompt drawn/saved, Mock diagnostic completed, GeoExtract completed automatically, polygon visible, reject then accept saved. Export link exercised; Next HTTP GeoJSON content independently validated.
- Browser demo survives infrastructure restart. One accepted feature exported to ignored artifacts/mock-geoextract-demo.geojson. This file contains synthetic test data, no credentials.

Mock results use mock-v1 and constant synthetic probability 0.75. No research model, GPU, paid service or cloud runtime was enabled. Current bounded AOI window is at most 4 million source pixels / 512 output pixels per longest edge; large-AOI tiling is a later phase. Rasterio/Affine/NumPy deprecation warnings are recorded by tests; tests pass.

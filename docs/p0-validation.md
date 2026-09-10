# P0 local validation — 2026-09-11

Status: P0 implementation and local runtime acceptance PASS.
This report covers P0 only. Git author is configured locally for this repository.
Delivery branch: feat/geoai-mvp. Git remote history is the authority for commit/push status.

## Environment
- macOS Darwin, arm64; Docker Desktop Engine 20.10.17 / Compose 2.10.2.
- nvm v0.40.7 installed from official release into ~/.nvm (Homebrew bottle failed).
- Node 24.21.0, npm 11.19.0, pnpm 12.3.4 verified in fresh interactive zsh.
- .nvmrc, packageManager and pnpm-lock.yaml pin JS environment.
- Host Python venv created with local Codex bundled Python 3.12.14.
- Container PostgreSQL 17.6 aarch64, PostGIS 3.3.
- Container Rasterio 1.4.3 / GDAL 3.6.2; host GDAL 3.9.3. COG driver available.

## Checks actually executed
| Check | Result |
|---|---|
| pnpm install --frozen-lockfile | PASS |
| pnpm build | PASS, including final /health page |
| pnpm typecheck | PASS |
| pnpm lint | PASS |
| pnpm test | PASS, 1 static browser-secret boundary test |
| pytest services/api/tests | PASS, 13 tests |
| ruff check services/api scripts | PASS |
| pip check | PASS |
| Upstream byte integrity | PASS, 25 files, exact commit lock |
| Docker Compose config | PASS |
| Docker local image builds and up | PASS |
| All 14 enabled services | healthy |
| SELECT version(); SELECT PostGIS_Version(); | PASS |
| Private probe schema grants / RLS | anon/authenticated have no USAGE; RLS enabled |
| Auth admin create / password login / get-user / cleanup | PASS |
| PostgREST | PASS |
| Realtime WebSocket heartbeat | PASS |
| Storage upload / download / HEAD / signed URL / delete / missing | PASS |
| Redis PING / Raster heartbeat | PASS |
| Database + object + Redis data across compose restart | PASS |
| FastAPI readiness | PASS, nine checks ok |
| Next.js to FastAPI proxy | PASS, nine checks ok |
| Browser | PASS: Docker homepage → /health; all nine statuses visible as ok |

Actual full integration command: `.venv/bin/python scripts/acceptance.py`.
Final Web rebuild and browser check followed the full integration run; backend/storage
configuration did not change. HTTP /api/health was also checked directly.
Local build/test results are independent of GitHub Actions. No GPU inference claim.

## Issues found and corrected
- BuildKit Docker Hub token timeout: pre-pulled fixed Python/Node bases via Docker daemon.
- Linux arm64 Rasterio source build: installed GDAL development libraries in image.
- macOS system SOCKS proxy interfered with local WebSocket: explicit proxy=None.
- Storage v1.74.0 returns HTTP 400 with NoSuchKey/404 for absent objects: exact normalization,
  with regression tests confirming unrelated authorization errors still propagate.
- Restart readiness is asynchronous: bounded actual readiness polling, no unconditional pass.
- Review found missing Web→API acceptance: added endpoint and exact dependency assertions.
- In-app browser blocks raw JSON navigation: P0 HTML /health provides visible verification.

## Limits
One Starlette/AnyIO deprecation warning remains in host tests; no test failures.
Repository contracts have no business implementations in P0. Auth login UI, membership
RLS, raster processing jobs, real models and export remain later phases. Raster Worker
currently validates the GIS runtime and emits heartbeat; it does not process jobs.
Restart persistence is verified; disaster recovery, volume backup/restore and production
hardening are not claimed. Supabase Storage local backend is tested; no S3-provider claim.

## Current local endpoints
- Web: http://127.0.0.1:3000
- Readable health: http://127.0.0.1:3000/health
- FastAPI: http://127.0.0.1:8080/health/ready
- Supabase gateway/Studio: http://127.0.0.1:8000 (credentials only in local .env)

All real credential files are ignored and mode 0600. Secret files are excluded from Git delivery.

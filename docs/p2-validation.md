# P2 local validation · 2026-09-11

Base: bf098db on feat/geoai-mvp. MapLibre GL pinned to 6.9.0.

PASS: host and Docker build, typecheck, ESLint, 3 frontend tests, 17 backend tests, Ruff.
PASS: real workspace SSR owner access, cross-user private project denial, unauthenticated redirect. P1 API/RLS/BFF regression remains passing.
PASS: worker and shared module served from local Web with JavaScript MIME type.
PASS: browser WebGL graticule visible; load complete; zoom 1.00 -> 2.00; reset -> 1.00; navigate to project settings and return with a fresh ready map.
PASS: local container health checked before commit.

Browser verification found MapLibre 6's Next.js worker URL requirement. Fixed by copying both worker and shared module from locked node_modules into public/maplibre during dev/build and including public in standalone Docker image. Initialization has a 30-second error deadline. Official reference: https://maplibre.org/maplibre-gl-js/docs/#installation

Offline coordinate canvas has no external basemap or font dependency. Raster upload/display is intentionally deferred to P3/P4.

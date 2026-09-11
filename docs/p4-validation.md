# P4 local validation · 2026-09-11

Base accda03. Local macOS arm64, 14 Docker services.

PASS: host/Docker production build, typecheck, lint, frontend tests, 29 backend tests, Ruff.
PASS: real Worker conversion -> COG LAYOUT/block size, thumbnail PNG, original CRS/dimensions/bands, PostGIS footprint validity/location, Storage HTTP Range 206.
PASS: nonempty georeferenced XYZ tile, fully transparent outside tile, cross-user tile denial, Next tile delivery.
PASS: failed asset retry permitted for owner, denied for viewer, successful reprocessing.
PASS: RGBA and gray+alpha rendering; shared display ranges preserve identical colors across tiles; real child-process timeout termination and parent cleanup even after simulated Redis heartbeat failure.
PASS: >10 MiB upload/storage/RLS regression, waiting for worker completion before QA cleanup.
PASS: browser retry failed QA asset -> automatically shows ready EPSG:4326, 256x256, 3 bands -> fits map -> actual colored checkerboard raster visible.
PASS: Supabase security advisors (no issues) and database/Storage/Redis restart persistence regression.

Warnings: installed Rasterio/NumPy/Affine emit deprecations; unreferenced PNG test images emit expected NotGeoreferencedWarning. GeoTIFF/COG CRS and PostGIS geometry are explicitly tested.

Preserved original QA file while fixing a temporary SQL parameter mismatch; it was retried through the product UI after the fix. No original raster was overwritten or deleted.

# P3 local validation · 2026-09-11

Base 9c5feb8; macOS arm64, local Docker, feat/geoai-mvp.

- PASS host/Docker build, typecheck, lint (generated MapLibre vendor files excluded), frontend tests.
- PASS 23 backend tests and Ruff; includes TIFF signature/filename validation, declared/chunked upload size limit and committed/uncertain registration response loss.
- PASS actual >10 MiB GeoTIFF through same-origin Next route with expired access cookie + valid refresh; checksum and bytes preserved through Storage download.
- PASS SQL size/checksum metadata; viewer download; public bucket access denied.
- PASS malformed TIFF, unauthorized/cross-project/viewer upload denial; Origin rejection and direct PostgREST RLS.
- PASS browser local fixture selection, upload success message and asset list/download link.
- PASS P1 Auth/RLS/BFF and P2 workspace regressions.
- PASS Supabase security advisors and final container health checks.

Review corrections: streaming route excluded from Next proxy's default 10 MiB body-copy limit; session refresh performed before direct streaming. Metadata timeouts reconcile by generated UUID and never delete possibly committed source objects. No real user data used; browser QA asset retained for P4 conversion.

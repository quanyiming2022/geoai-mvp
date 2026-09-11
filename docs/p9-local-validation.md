# P9 local validation — 2026-09-11

**P9 = IN PROGRESS.** Stable P8 tag `v0.1.0-p8` was pushed. Current branch: `feat/p9-real-model-worker`; This is a user-authorized interim source-control snapshot, not P9 completion. No P10/P11 work.

## Implemented and locally verified

- Versioned URL-free Worker contract, exact 512 RGB/binary inputs, finite probability response, model identity, seed, bounded HTTP retries/total timeout and cancellation.
- Administrator registry/CRUD/Test Connection, research policy, server-side secret references, config revision invalidation and stale-probe fencing. Ordinary users see only sanitized enabled endpoint choices.
- Independent support/query raster tile jobs, durable queue, probability/binary/valid GeoTIFF artifacts, native affine, PostGIS polygons with actual confidence and perimeter, review/export and protected artifact downloads.
- Synthetic E2E used two distinct 1024×1024 rasters, query offset (201,307), unchanged source resolution, nonconstant output. Cancellation/old attempt persistence rejected; exact idempotent replay survives endpoint disable; new request rejected.
- Actual probability/mask/valid downloads and PNG support preview API fixture PASS. These are synthetic fixtures, not SkySense++ quality acceptance. Metrics remain in ignored `artifacts/p9-tile-acceptance.json` and `artifacts/p9-http-fixtures.json`.
- Backend 62 tests PASS; frontend 3 tests PASS. Build/typecheck/lint PASS at reviewed workspace revision. P8 full local regression PASS, including Auth/RLS/raster/prompt/queue/review/audit/Next export.
- Supabase upstream integrity: 25 files unchanged. Database/PostGIS/Redis/Storage restart persistence and local API/Web integration PASS on repeat. First run failed at its final health snapshot after successful persistence/API checks; all 15 containers were subsequently healthy. Added sanitized container identity diagnostics, with no relaxed check or production workaround.

## UI state

- Real `qym57@outlook.com` administrator session verified in IAB. Research-only `SkySense++ Research · 待配置权重` model saved with version `unconfigured`, no checkpoint and no endpoint activation. No temporary test administrator grant occurred.
- Map-centered shell, resource tabs, collapsible/resizable panels, layer visibility/opacity, focus mode, drawing/undo shortcuts, support preview, extraction steps, bottom jobs, selection/highlight and review Inspector implemented.
- IAB verified map rendering, focus mode, hide-layer state surviving tab switching, drawing/Inspector activation, preview error state, Backspace from 3 to 2 points disabling Save, and Escape cancellation. Draft was discarded; no test prompt added to the user's project.
- Valid preview API PASS. Desktop Control Center and navigation screenshots at 1440×900 / 1920×1080, Workspace drawer identity, dirty navigation guard and view restoration are documented in `control-center-validation.md`. Full real-model visual review remains pending GPU fixtures.
- User subsequently logged into the visible administrator browser manually. Desktop checks used that authenticated session; no credential copying or test-account administrator promotion was used.

## Research GPU bridge

Remote-only `services/model-worker/research_adapter.py` pins official source/weights and encapsulates support/query composition, hidden query annotation, seeded/reset vocabulary, normalization and query-half probability extraction. CPU layout test PASS. Remote README explains setup requirements and Python/CUDA dependency validation. No fake output substitutes for loading failure.

User GPU/server/weights are unavailable. Real loading, CUDA determinism, three actual semantic fixtures, probability quality, latency and GPU memory remain unverified. This is not a verified GPU container or P9 COMPLETE.

## Review

All bounded review findings fixed and rechecked: release/endpoint health invalidation, stale health writes, total streaming deadline, idempotent replay after endpoint edits, and layer-control state surviving tabs. Actual cancelled/old-attempt result persistence rejection was also verified.

Archive scope: preserve current Worker/registry/single-tile scaffolding and management UI as an interim baseline on the development branch. The user authorized pushing now and submitting further commits after configuration. Real P9 GPU acceptance stays pending user server/weights. Advanced multi-shot/language/monitoring/tiling remain out of scope.

# Workspace visual polish — 2026-09-11

Status: implementation and local checks complete; desktop screenshot acceptance pending.

The user accepted the current Workspace information architecture. This pass retains the header, left vertical navigation and object panel, map, right contextual panel, and collapsed jobs drawer. No new layout restructuring or P8/P9 backend, API, database, or test changes are part of this pass.

Changes:
- Consistent local stroke SVG icon set for object navigation and map tools.
- Unified hover, selected, keyboard focus, border and shadow treatments.
- Compact asset names, readable processing states and decimal MB display; original filename remains in title and properties.
- Compact Run Extraction CTA. No fabricated current model identity.
- Empty Inspector explains available object properties.
- Breadcrumb-like header and restrained job status typography/progress.

Checks already run locally during this work:
- Typecheck PASS; lint PASS; frontend tests 3 PASS.
- Backend regression: 62 PASS.
- P8 real service acceptance PASS, including COG, Prompt, AOI, durable job, Mock result, review, export, SQL RLS and immutable original/audit history.
- In-app logged-in browser: map visible, object navigation, raster Inspector selection and Focus Map checked. Final polish reloaded and visually inspected in the available narrow viewport: unified SVG rail/tool icons, asset labels, compact CTA and empty-state copy render correctly. This is not desktop acceptance.
- Final Docker Web build PASS; Web container recreated successfully.

Remaining acceptance:
- Final polished UI screenshot and interactions in 1440×900 and 1920×1080.
- Save genuine before/after screenshot files; screenshots have not been fabricated or substituted with narrow browser images.
- Independent browser test-account login authorization is pending after an earlier automatic approval rejection. The current in-app authenticated browser remains available but has a narrow viewport.

Do not mark screenshot acceptance complete or commit/push based only on compilation.

## Final interaction polish

- Kept accepted five-part layout unchanged; upload form is always visible.
- A sole ready raster is selected on workspace entry and its properties appear immediately.
- Extraction launcher explicitly distinguishes built-in Mock from registered model Worker. Missing eligible raster, persisted visual prompt, AOI, or healthy Worker endpoint disables the CTA and lists missing conditions. Mock retains its local model and original API path.
- In the real admin browser session, verified default raster selection, visible upload, missing visual prompt message, and Worker missing healthy endpoint message. No jobs were submitted from this user's project during these checks.
- Fresh frontend typecheck/lint/3 tests and Docker build PASS.
- Fresh backend 62 tests and P8 full service acceptance PASS.
- P9 single-tile acceptance PASS with `PYTHONPATH=services/api .venv/bin/python scripts/acceptance_p9_tile.py`: registered HTTP channel, separate support/query rasters, native 512 window, nonconstant probabilities, PostGIS, review/export. Synthetic only; no GPU/checkpoint performance claim.
- UI structural work is stopped. Real SkySense++ GPU/checkpoint/endpoint configuration and desktop screenshot acceptance remain outstanding.

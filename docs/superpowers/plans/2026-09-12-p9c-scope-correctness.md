# P9C execution scope correctness plan

**Goal:** preserve whole-AOI intent without pretending that single-tile inference scans an AOI.
**Architecture:** explicit assistant execution_scope and server capability gate; an authenticated read-only map-point resolver supplies the unchanged single-tile Job contract. No inference, schema migration or adapter changes.
**Spec:** user-approved P9C correctness fix, preceding P10.

- [x] Distinguish full_aoi / single_tile, retain AOI context, block unavailable full_aoi before coordinates or LLM availability can obscure the response. No runnable draft on rejection.
- [x] Preserve the existing manual Job payload; replace pixel inputs with map point → CRS transform → bounded native 512 window → visible outline.
- [x] Show raster, AOI, visual prompt, model, scope and capability in drafts; selecting a test window is an explicit scope change requiring a new draft and confirmation.
- [x] Run backend/frontend/typecheck/lint/build and unchanged P8/P9 acceptance. Verify actual browser unavailable response and map-selection path.
- [x] Document evidence, independently commit, then stop for the handoff to P10. No P11 or product expansion.

Files: `services/api/geoai/llm.py`, new `map_window.py`, assistant/map/manual form components and scoped assistant server-action route. Tests: `test_llm_scope.py`, `assistant-scope.test.mjs` and existing acceptance scripts. Frozen baseline: `4533a79`.

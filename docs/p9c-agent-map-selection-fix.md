# P9C assistant map selection correction

Base: `df76566` / `v0.2.0-p9c.2`. This is a P9C correctness patch, not P10.

## Root causes and changes

- Full-AOI capability rejected all unavailable ranges with the same map-selection action. A disjoint AOI could therefore never complete that action. Invalid coverage now asks for a replacement AOI or new drawing and resumes the original goal. Too-small source imagery asks for another raster.
- Coverage previously checked size before source bounds, misclassifying a large off-image AOI as a multi-tile requirement. Source coverage is checked first. Native 512-pixel inputs and model preprocessing are unchanged.
- Map-start errors left a pending assistant selection despite no map listener being active. Failed starts now release waiting state, recheck invalid AOIs, and avoid duplicate instructional messages.
- Restoring a session no longer restores a map wait without its transient map listener. Conversation and pending intent remain available for retry.
- Map selection became active during camera fly-to. A user click could stop that transition outside a small AOI. Entering test selection now positions the camera immediately before accepting the click.
- Choosing a replacement AOI/raster clears stale coordinates and old name hints. Cancelling a draft clears its temporary footprint.

## Verification

- Backend: 144 tests PASS, including disjoint AOI repair/continuation, named-resource replacement, oversized off-image range classification, small/full-range capability and existing P8/P9 unit coverage.
- Frontend: 6 tests PASS; typecheck, lint and production build PASS.
- Local synthetic Worker HTTP regression PASS (determinism and cancellation; not a new GPU capability claim).
- Browser 1440×900 and 1920×1080: Enter sends, test selection compacts assistant, actual map click produces confirmation, cancel/retry works, disjoint AOI offers replacement/drawing, replacement continues original intent, refresh during selection permits retry. No inference submitted by this browser test.
- Reproducer: `scripts/acceptance_agent_map_browser.py`; use `acceptance_small_aoi.py setup` and an ordinary fixture-owner browser login first. The browser regression adds its off-image AOI only to that isolated fixture. Cleanup uses the existing reference-preserving `acceptance_small_aoi.py cleanup`.

Local evidence (ignored artifacts): `agent-map-browser.log`, `agent-map-fix-backend.log`, `agent-map-fix-frontend.log`, `agent-map-fix-typecheck.log`, `agent-map-fix-lint.log`, `agent-map-fix-deploy.log`, `agent-map-fix-p9-http.log`, `agent-map-confirm-1440.png`, `agent-map-confirm-1920.png`, `agent-map-repair-1440.png`.

No changes to SkySense++ adapter, preprocessing, slot/query-half, inference contract, probability/threshold pipeline, database schema or authorization policy. Original A/B/C/D benchmarks are retained. P10 experiments have not started.

## Follow-up: automatic AOI coverage and choose-or-create

The final interaction rules supersede the earlier small-AOI explicit-test behavior:

- A selected AOI fitting a native 512×512 window is automatically covered and requires only execution confirmation, including a request phrased as a test. No second map click is requested.
- Larger AOIs can use a deliberate local test. Only that user-picked preview renders a temporary blue dashed window. Automatic AOI coverage never renders it. Cancel/close and terminal job updates hide the preview; input snapshots remain intact.
- Resource clarification includes creation even when candidates already exist: AOI drawing, visual-prompt drawing, and a reused upload/library component for rasters. Raster processing completion resumes the saved continuation. Names with multiple matches require clicking a choice; real timestamps, dimensions and available class labels distinguish choices.
- A missing explicit target no longer defaults to the first of several rasters. A unique geographic covering candidate may initialize it. An explicitly selected incompatible raster is not silently replaced: the UI offers the covering raster by name, preserving the AOI.
- The actual user AOI `333` is inside `SPOT6_RVB_1M00_2019_10014.tif`, not the project's `10048`/`10008` scenes. Read-only validation against the current stored COG gives 276.402908 × 166.728228 source pixels, automatic offset col=622/row=215. No user geometry was changed.

Follow-up evidence:

- Backend 151 tests; frontend 8 tests; typecheck/lint/build.
- Actual browser: multiple rasters → upload from assistant → processing → resume AOI clarification → draw/save AOI → full-AOI confirmation without retyping. Evidence: `artifacts/agent-resource-auto-confirm.png`.
- Actual browser: wrong target + existing AOI → choose covering raster → Next enabled, same AOI. Evidence: `artifacts/aoi-existing-target-recovered.png`.
- `scripts/acceptance_aoi_window_browser.py`: small AOI auto/no blue; large AOI local selection/blue; close clears it. Evidence: `artifacts/agent-resource-window-browser.log`, `aoi-auto-no-blue-1440.png`, `aoi-local-blue-1920.png`.
- Updated manual draw/save/return regression passes with the requested small-AOI auto semantics: `artifacts/agent-resource-manual-regression.log`.
- Current COG proof: `artifacts/aoi-333-authoritative-coverage.json`.
- Existing local synthetic worker HTTP regression still passes; no new claim of model capability.

Final rerun: `agent-resource-map-regression.log` PASS (multi-raster clarification, map selection, cancel/retry, off-image AOI replacement, refresh/retry at both desktop sizes). Production web build and all 15 local container health checks pass. The authorized isolated fixture was cleaned with reference protection; see `agent-resource-cleanup.log`. Changes remain uncommitted.

## Superseding product decision: AOI-only extraction

The user approved removal of the separate local-test interaction. The earlier blue-preview rules and point-selection browser evidence above are historical, not current acceptance criteria.

Current product behavior: a saved AOI is required for real inference; a fitting AOI receives an automatic native-resolution window and explicit confirmation; an oversized AOI offers selection/creation of a smaller AOI. No map point picker or blue query footprint is rendered. Legacy conversation cards are migrated to AOI re-evaluation, retaining history. Existing diagnostic APIs, benchmark scripts, model adapter, probability clipping and immutable job inputs remain unchanged.

Current browser reproducer: `scripts/acceptance_aoi_only_browser.py`. Legacy point-selection browser entrypoints now delegate to this AOI-only acceptance. Model benchmark scripts are unchanged.

AOI-only verification: backend 153 tests PASS; frontend 8 tests PASS; typecheck/lint and local production build PASS. Actual 1440×900/1920×1080 browser checks cover small-AOI automatic confirmation, large-AOI blocking, manual cancel/save returning to the same step, assistant creation resuming the pending task, and absence of point-selection controls/blue overlay. Local synthetic HTTP determinism/cancellation PASS, without claiming a new SkySense++ capability result. Authorized isolated test project/account cleaned; no user project changes. Evidence: `artifacts/aoi-only-{backend,frontend,typecheck,lint,browser,manual,http,final-build,cleanup}.log`, `aoi-only-large-1440.png`, `aoi-only-assistant-1920.png`. This is an uncommitted P9C simplification, not P10/P11.

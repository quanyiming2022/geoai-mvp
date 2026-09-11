# Control Center and Workspace navigation validation

Date: 2026-09-11. Local macOS arm64, Docker Compose deployment, branch `feat/p9-real-model-worker`.

## Delivered presentation

- Shared persistent `/control` layout: `/control/projects`, `/control/models`, `/control/system`.
- Compatibility redirects retain old `/projects`, `/settings/models`, `/system/status` entry points; standalone project settings routes remain.
- Projects retain reusable master-detail overview/members/settings. Workspace remains `/projects/:id/workspace`, without management navigation.
- Models and nodes use a resource navigator and detail panel. Existing server actions and registry API payloads are reused; no provider/worker/DB contract changes in this iteration.
- Health uses the existing checks, a grouped service matrix and detail drawer. No latency, hardware or event history is fabricated.
- Compact metrics match the project visual language. System summary contains three metrics only; duplicated top-level check time was removed on request. Check timestamps remain in the service matrix and diagnostics.
- Workspace project menu opens overview/settings/members in place. Navigation guard covers geometry and form drafts, including multi-step form fields; settings report their actual dirty state. Durable jobs do not block navigation.
- Session view state is scoped by user and project: map center/zoom, visibility/opacity, active left panel, inspector, selected object, collapsed panels and Mock/Worker channel. Only view preferences are stored, no tokens or business records.

## Executed checks

- `pnpm typecheck`: PASS.
- `pnpm lint`: PASS.
- `pnpm test`: 3 PASS.
- Local Docker Web production build: PASS.
- Backend pytest: 62 PASS (existing dependency deprecation warnings).
- `scripts/acceptance_project_settings.py`: PASS, including owner writes, editor/viewer restrictions, outsider denial and direct PostgREST RLS.
- `scripts/acceptance_p8.py`: PASS, including raster/COG/prompt/AOI/Mock job/PostGIS/review/export and immutable prediction/audit checks.
- `scripts/acceptance_p9_tile.py`: PASS — registered HTTP worker, native-resolution 512 window, nonconstant probabilities, PostGIS, review/export; **synthetic only**.

## Browser evidence

Using the administrator's manually authenticated Chrome session, pinned to the verification tab:

- Primary navigation Models → System retained the same Header DOM node (`sameShell: true`).
- Workspace overview drawer retained the same canvas and pathname (`sameMap: true`).
- Unsaved AOI name → return to Control Center displayed the leave-confirmation dialog. Continue retained both draft text and canvas.
- Leave/re-enter same project restored hidden raster, Layers panel and exact settled zoom (`zoomRestored: true`, Zoom 15.65). Default view restored after testing.
- At 1440×900 and 1920×1080: no horizontal document overflow on models, selected model, empty compute and system views.
- System has exactly three compact metrics; models has four.
- Earlier ordinary-user browser verification denied infrastructure details; new shared layout and system page retain the same server-side administrator check.
- Temporary ordinary browser QA accounts and their test projects were removed; real project records were not changed.

Screenshots (local, ignored artifacts):

| View | 1440×900 | 1920×1080 |
|---|---|---|
| Models | [models](../artifacts/control-models-1440.png) | [models](../artifacts/control-models-1920.png) |
| Model detail | [detail](../artifacts/control-model-detail-1440.png) | [detail](../artifacts/control-model-detail-1920.png) |
| Compute empty | [compute](../artifacts/control-compute-1440.png) | [compute](../artifacts/control-compute-1920.png) |
| System | [system](../artifacts/control-system-1440.png) | [system](../artifacts/control-system-1920.png) |
| Service drawer | [drawer](../artifacts/system-service-detail-1440.png) | [drawer](../artifacts/system-service-detail-1920.png) |

[Unsaved navigation guard](../artifacts/workspace-navigation-guard.png)

## Remaining external dependency / limits

No real GPU server or checkpoint is configured. Therefore real-node hardware detail, actual SkySense++ inference/performance, and real-server offline UI cannot be accepted from these screenshots. P9B remains pending external GPU/weights. The model test control explicitly refers users to the existing Workspace single-tile inference flow; it does not fabricate a model test.

Existing API requires a node to be enabled before connection testing. UI retains this contract and explains it; saved/enabled alone does not imply healthy or available. System check history and latency are not yet collected.

No P10/P11, tiling/stitching, main merge or P9-complete claim.

Final navigation recheck: native `history.back()` with an unsaved project-settings name was intercepted before traversal. Continue Work retained `?panel=settings`, the open drawer, and exact draft text. Draft was then reverted to the saved name without submitting, drawer closed, and Control Center opened. Chrome Navigation API provides the pre-navigation interception; older browser fallback uses popstate/beforeunload and is not separately browser-certified in this run.

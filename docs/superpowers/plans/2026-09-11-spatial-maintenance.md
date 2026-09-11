# Spatial resource maintenance implementation plan

Goal: editable/deletable AOIs and visual prompts without changing submitted Job inputs.
Spec: latest user-approved AOI/Prompt maintenance scope and P9B acceptance; frozen model adapter.
Architecture: soft-deleted resources retain foreign keys; insert-time immutable JSON execution snapshots freeze geometry and raster/storage references. Prompt edits stage unique object versions before a compare-and-swap database update. Existing authenticated repositories and project RLS remain the authorization boundary.

- [x] Add SQL regression for snapshot immutability, owner/editor writes, viewer denial, stale edits and deleted-resource submission rejection.
- [x] New migration: resource revision/deleted_at/updated_by, audit, immutable Job input snapshot (legacy backfill explicitly labeled), versioned prompt artifact constraints. Preserve existing FK history.
- [x] AOI PUT/DELETE and Prompt PUT/DELETE with revision conflicts; staged crop/mask regeneration, cleanup only uncommitted new paths. Legacy and versioned artifact download validation.
- [x] P8/P9 executors read frozen inputs; preserve native-window/preprocessing behavior. Include snapshot provenance in output.
- [x] Reuse list menus and map drawing for geometry reshape; explicit Save/Cancel, deletion confirmation and selection cleanup; retain dirty navigation guard.
- [x] Run backend/frontend/typecheck/lint/build; local SQL/API permission and snapshot tests; P8/P9 synthetic and real smoke; actual browser maintenance/review/export.
- [x] Update final report with evidence and unresolved limitations. Do not claim model capability PASS or start P11.

Prior work retained: actual GPU stop/recovery and browser post-recovery Job succeeded; original A/B/C/D artifacts remain unchanged.

# Raster Asset Library and assistant revision controls

User requested local implementation without commit/push. Base 6921606 was pushed before this instruction arrived; all following changes stay uncommitted.

## Scope and invariants

1. Edit an earlier user message and resend from that point. Discard only later conversational UI branches, never undo submitted jobs. Cancel in-flight language HTTP generation with an owner/project-bound request identity; ignore stale UI responses. Existing durable jobs use the existing confirmed cancellation API.
2. Platform asset identity, immutable storage namespace, project alias links. Backfill one link for each legacy raster, preserve existing source/COG/thumbnail bytes and processing metadata. No copy or reprocess on linking.
3. Asset visibility: owner/platform admin or member of a linked project. Only accessible assets participate in deduplication responses. Project editors manage links/aliases; global asset mutation requires asset owner/platform admin. No shared AOI/prompt/job/result visibility between projects.
4. Unlink is separate from asset deletion. Reject deletion while active links exist. Soft-delete assets retained by historical evidence; immutable files remain available to their historical jobs. No physical purge of evidence in this release.
5. Migrate project-scoped foreign keys and read checks to explicit links while retaining project ownership of business objects and RLS. Resolve storage through immutable asset identity instead of reconstructing paths from the current project. Keep legacy paths valid. Existing job snapshots remain unchanged.
6. Library master-detail route /control/rasters with true metadata/filter/reference count. Workspace item menu and add-existing selector. Duplicate upload prompts explicit reuse and avoids second storage/COG generation.
7. Validate upload, alias, reuse, same COG, unlink isolation, delete restrictions, viewer/outsider, retained snapshots plus P8/P9 and real native-window smoke. Test UI and assistant edit/stop. Do not commit/push; no P10/P11 or model changes.

## User follow-up after the above work

Keep the existing raster row actions (show on map / zoom / create visual prompt) in place. Add result object maintenance afterward: name/description, existing reviewed geometry vertex editing with save/cancel, soft delete and selection synchronization, per-result export using current geometry/name and original provenance. Preserve original prediction, Job/snapshot and append-only review/audit. Validate role rejection, original evidence unchanged and P8/P9. No commit/push.

## Latest accepted UI correction

Raster inline actions are now show/hide, create visual prompt, and the more menu on one row. Raster name locates the image; all resource menus omit duplicate locate actions. Assistant conversations are archived locally on New, with one collapse control. Manual coverage inherits current selections. AOI/prompt creation now returns in place to avoid destroying the pending conversation.

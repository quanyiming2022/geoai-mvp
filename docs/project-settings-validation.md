# Project Settings validation — 2026-09-11

Implemented a settings-only page with General, Members and Permissions, Danger sections, and a primary map workspace link. No Workspace, Raster, Prompt, Job, Review, Export, database schema or RLS changes in this task.

General editing uses a client-local form and server action with a disabled pristine save button and in-place success notification. Current editor project-write permissions are retained. Roles remain owner/editor/viewer; no fictitious admin role. Delete remains disabled.

Members show email, actual role and joined state. Only owners see write actions. A native modal accepts an existing account email; no email is sent. A project-access-scoped identity endpoint returns member email; exact-email addition checks ownership before reading auth.users and writes membership through the caller's PostgREST token and existing RLS. No public account directory or browser service key. Project IDs are under developer details.

## Actual local checks

- Next build / TypeScript / ESLint / 3 frontend tests PASS.
- Backend 62 tests PASS.
- `scripts/acceptance_project_settings.py` PASS: owner updates/adds/changes/removes, invalid account, unsupported admin role, editor/viewer denied member writes, viewer denied project write, outsider denied reads, direct PostgREST RLS denial.
- Existing P8 end-to-end acceptance PASS, including original prediction/audit/RLS/review/export.
- Existing P9 native single tile HTTP acceptance PASS; synthetic model only.
- Real browser owner: edit name and description, save without navigation, disabled clean save, add existing account by email as editor, immediate member listing, change to viewer, remove with confirmation.
- Real browser new member login: editor can read settings but sees no member write controls; after downgrade inputs are disabled; after removal settings returns 404.
- Desktop 1920 and narrow 390 viewport: no document horizontal overflow. 1440 screenshot visually inspected.
- Temporary browser users and isolated empty test project cleaned up. Actual user project data and members were not modified.

Screenshots stored locally:
- [1440 general settings](../artifacts/settings-1440-general.png)
- [1920 members](../artifacts/settings-1920-members.png)
- [390 narrow layout](../artifacts/settings-narrow.png)

P9 real GPU/checkpoint readiness and earlier Workspace desktop acceptance are separate outstanding work; this settings task does not claim them complete.

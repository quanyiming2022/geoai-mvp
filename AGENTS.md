# GeoAI Platform development constraints
Only repository: https://github.com/quanyiming2022/geoai-mvp.
Work at /Users/quanyiming/Projects/geoai-mvp on macOS arm64.
GitHub is source control and backup; actual acceptance runs locally.
P0 through P8 are authorized in order. Complete local acceptance, commit and push feat/geoai-mvp after each phase, then continue automatically. Do not start the next phase before the previous phase is verified and pushed.
Do not modify or merge main. Pause only for required credentials/login/authorization, payment, important data deletion/overwrite, unresolved infrastructure blockers or major architectural ambiguity.
Before work inspect pwd, git status/remotes/branch, uname, docker info.
Use .nvmrc and pinned pnpm. No sudo npm. Secrets only in ignored .env/.env.local.
Preserve upstream Supabase bytes. Customize only separate Compose override.
Exactly one PostgreSQL service: Supabase db with PostGIS extension.
Keep ObjectStorageProvider, Repository, ComputeProvider, ModelAdapter boundaries.
ResearchSkySensePPAdapter is research_only and unavailable until P9.
No commit or push until every local P0 acceptance check passes, including restart persistence.
CI does not replace local Docker, SQL, browser and integration verification.

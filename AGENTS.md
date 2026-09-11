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
P8 is COMPLETE and frozen at v0.1.0-p8. P9 is authorized on feat/p9-real-model-worker through P9A/P9A.5/P9B, including incremental map-first UX. Preserve P8 contracts/behavior and regression coverage. Stop after P9; never claim completion from fake inference when real LAN GPU/checkpoint verification is unavailable.
GeoExtract product direction: docs/geoextract-product-direction.md. Sample-defined target extraction, not image search or a SkySense++ frontend. P9 remains single visual support + one native-resolution tile. Preserve extensibility for reusable/versioned prompts, support_examples, negative examples, disabled experimental language fields, independent query raster, immutable GIS prediction/review provenance. Do not implement advanced levels early.

P9C is additionally authorized: optional local-default language task planning, configurable local/LAN/cloud LLM providers, existing resource lookup and explicit confirmation before original job creation. Keep manual workflows and all P8/P9 contracts. This does not authorize language-conditioned pixel prediction, advanced multi-shot, monitoring or P10/P11. Validate real local LLM separately from P9B pending GPU/checkpoint inference.

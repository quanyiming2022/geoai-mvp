# P1 local validation · 2026-09-11

Environment: /Users/quanyiming/Projects/geoai-mvp, macOS arm64, feat/geoai-mvp. P0 commit 9812bdf verified on origin before P1 began.

- Next.js host and Docker production build: PASS.
- Typecheck / ESLint / frontend tests (2): PASS.
- FastAPI pytest (17) / Ruff: PASS. One upstream Starlette/AnyIO deprecation warning remains.
- Existing Supabase PostgreSQL migrations applied transactionally; second application no-op: PASS.
- Supabase CLI 2.81.3 db advisors, security warn/error: no issues found.
- Real two-user API tests: private project isolation, viewer read-only, editor modification, owner membership management: PASS.
- Direct PostgREST and SQL RLS: owner spoofing denied, immutable owner, revoked member immediately cannot read/update: PASS.
- Real Next BFF with present expired and near-expiry access cookies plus valid refresh: replacement HttpOnly cookies and protected page: PASS.
- Auth refresh and logout refresh-token revocation: PASS.
- Full infrastructure regression including database, Storage, Redis restart persistence, all container health checks, FastAPI and Next-to-API: PASS.
- Browser at localhost: unauthenticated redirect, local signup, empty project list, create project, edit/save confirmation, logout, existing account login and preserved edited project after infrastructure restart: PASS.
- Original pinned Supabase files: 25 SHA256 hashes unchanged.

Review fixes: upstream Auth 5xx now maps to retryable 503 rather than invalid-session 401; existing expiring Cookie triggers refresh 60 seconds before JWT expiry. Real insert testing uncovered snapshot visibility in INSERT RETURNING; a follow-up migration adds an explicit owner predicate, with permission regression passing.

Browser test project/account are disposable local QA data, retained for subsequent phases. No private data or production accounts used. No cloud deployment or main merge performed.

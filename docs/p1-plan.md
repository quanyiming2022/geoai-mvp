# P1 Auth and Projects

Authorized scope: local Supabase Auth password login/signup/logout/refresh, protected project list/detail, project creation/edit, owner-managed editor/viewer membership. No map or raster features until P1 is verified and pushed.

Next.js is a server-side BFF: HttpOnly SameSite=Lax cookies, server actions for mutations with Origin protection; proxy refreshes sessions. FastAPI verifies every bearer with Supabase Auth. User-scoped PostgREST repositories forward the bearer and anon key, never service role for project access.

PostgreSQL projects and project_members use RLS plus explicit column grants. Non-exposed fixed-search-path lookup functions prevent recursive membership policies and return only permissions for auth.uid(). Owner is immutable through the Data API. Adding members uses their existing account UUID, avoiding a public user directory. All regular members can view member roles; only owners manage them.

Implementation and acceptance:
1. Schema migration and checksum-checked local migration runner, transaction and advisory lock.
2. Backend validation tests, Auth routes, user-scoped repository and project/member routes.
3. Login/signup screens, protected projects, member forms, refresh/logout.
4. Local unit/static/build checks, Docker rebuild, real Auth/API/RLS cross-user tests, restart persistence regression and browser sign-in/create/edit/logout.
5. Review, secret scan, commit and push feat/geoai-mvp. Then begin P2 automatically.

Local signup auto-confirms email, as configured in P0. Production email verification/SMTP is a deployment setting and requires actual SMTP credentials. No email invitations are sent in P1.

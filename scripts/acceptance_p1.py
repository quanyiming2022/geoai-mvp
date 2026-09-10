"""Local P1 acceptance: real Auth, FastAPI, PostgREST RLS and refresh revocation."""
import uuid
import base64
import json
import time
import httpx
from dotenv import dotenv_values
from migrate import ROOT, connection


def run():
    env = dotenv_values(ROOT / ".env")
    auth = env["SUPABASE_PUBLIC_URL"]
    api = "http://127.0.0.1:" + env["GEOAI_API_PORT"]
    deadline = time.monotonic() + 90
    while True:
        try:
            httpx.get(api + "/health/ready", timeout=15).raise_for_status()
            break
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    admin_key = env["SERVICE_ROLE_KEY"]
    users = []
    with httpx.Client(base_url=auth, timeout=20, headers={"apikey": admin_key, "Authorization": "Bearer " + admin_key}) as admin:
        try:
            sessions = []
            for _ in range(2):
                seed = uuid.uuid4().hex
                credentials = {"email": seed + "@example.test", "password": seed + "Aa1!"}
                user = admin.post("/auth/v1/admin/users", json={**credentials, "email_confirm": True}).raise_for_status().json()
                users.append(user["id"])
                login = httpx.post(api + "/auth/login", json=credentials, timeout=20).raise_for_status().json()
                sessions.append(login)
            print("PASS: two real Auth identities and API login", flush=True)
            with httpx.Client(base_url=api, timeout=20, headers={"Authorization": "Bearer " + sessions[0]["access_token"]}) as a, httpx.Client(base_url=api, timeout=20, headers={"Authorization": "Bearer " + sessions[1]["access_token"]}) as b:
                assert httpx.get(api + "/projects", timeout=10).status_code == 401
                assert httpx.get(api + "/projects", headers={"Authorization": "Bearer invalid"}, timeout=10).status_code == 401
                p = a.post("/projects", json={"name": "P1 acceptance", "description": "Disposable test project"}).raise_for_status().json()
                path = "/projects/" + p["id"]
                assert a.get(path).raise_for_status().json()["my_role"] == "owner"
                assert b.get(path).status_code == 404
                assert all(row["id"] != p["id"] for row in b.get("/projects").raise_for_status().json())
                assert b.patch(path, json={"name": "forbidden"}).status_code == 404
                print("PASS: unauthenticated and cross-user project isolation", flush=True)
                a.post(path + "/members", json={"user_id": users[1], "role": "viewer"}).raise_for_status()
                assert b.get(path).raise_for_status().json()["my_role"] == "viewer"
                assert b.patch(path, json={"name": "forbidden"}).status_code == 403
                assert b.post(path + "/members", json={"user_id": users[0], "role": "editor"}).status_code == 403
                a.patch(path + "/members/" + users[1], json={"role": "editor"}).raise_for_status()
                assert b.patch(path, json={"name": "Editor saved"}).raise_for_status().json()["name"] == "Editor saved"
                assert b.patch(path + "/members/" + users[1], json={"role": "viewer"}).status_code == 403
                print("PASS: viewer/editor/owner permission matrix", flush=True)
                with httpx.Client(base_url=auth + "/rest/v1", timeout=20, headers={"apikey": env["ANON_KEY"], "Authorization": "Bearer " + sessions[1]["access_token"], "Prefer": "return=representation"}) as direct:
                    assert direct.patch("/projects", params={"id": "eq." + p["id"]}, json={"owner_id": users[1]}).status_code == 403
                    assert direct.post("/projects", json={"name": "spoofed", "owner_id": users[0]}).status_code == 403
                    assert direct.patch("/project_members", params={"project_id": "eq." + p["id"]}, json={"role": "viewer"}).raise_for_status().json() == []
                    a.delete(path + "/members/" + users[1]).raise_for_status()
                    assert direct.get("/projects", params={"id": "eq." + p["id"]}).raise_for_status().json() == []
                    assert direct.patch("/projects", params={"id": "eq." + p["id"]}, json={"name": "revoked"}).raise_for_status().json() == []
                assert b.get(path).status_code == 404
                with connection() as c:
                    c.execute("SET LOCAL ROLE authenticated")
                    c.execute("SELECT set_config('request.jwt.claims', %s, true)", ('{"sub":"' + users[1] + '","role":"authenticated"}',))
                    assert c.execute("SELECT id FROM public.projects WHERE id=%s", (p["id"],)).fetchall() == []
                    assert c.execute("UPDATE public.projects SET name='denied' WHERE id=%s RETURNING id", (p["id"],)).fetchall() == []
                print("PASS: direct Data API and SQL RLS, immutable owner, immediate revocation", flush=True)
                # Exercise the real Next proxy with present expired/nearly-expired cookies.
                # Forged exp is a scheduling hint only, never accepted as identity.
                web = "http://127.0.0.1:" + env["GEOAI_WEB_PORT"]
                refresh_token = sessions[1]["refresh_token"]
                for expires in (0, int(time.time()) + 30):
                    payload = base64.urlsafe_b64encode(json.dumps({"exp": expires}).encode()).decode().rstrip("=")
                    with httpx.Client(base_url=web, timeout=30, follow_redirects=True) as browser:
                        browser.cookies.set("geoai-access", "header." + payload + ".invalid")
                        browser.cookies.set("geoai-refresh", refresh_token)
                        page = browser.get("/projects").raise_for_status()
                        assert page.url.path == "/projects" and users[1] in page.text
                        changed = page.headers.get_list("set-cookie")
                        assert any("geoai-access=" in row and "HttpOnly" in row for row in changed)
                        refresh_token = next(row.split(";",1)[0].split("=",1)[1] for row in changed if row.startswith("geoai-refresh="))
                print("PASS: real Next BFF refreshes expired and near-expiry cookies", flush=True)
                refreshed = httpx.post(api + "/auth/refresh", json={"refresh_token": sessions[0]["refresh_token"]}, timeout=20).raise_for_status().json()
                a.headers["Authorization"] = "Bearer " + refreshed["access_token"]
                assert a.get("/auth/me").raise_for_status().json()["id"] == users[0]
                a.post("/auth/logout").raise_for_status()
                assert httpx.post(api + "/auth/refresh", json={"refresh_token": refreshed["refresh_token"]}, timeout=20).status_code == 401
                print("PASS: refresh and logout revoke refresh session", flush=True)
        finally:
            for user in users:
                admin.delete("/auth/v1/admin/users/" + user).raise_for_status()
    print("PASS: P1 live integration; disposable users/projects cleaned up", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL: " + type(exc).__name__ + " (secrets suppressed)", flush=True)
        raise SystemExit(1) from None

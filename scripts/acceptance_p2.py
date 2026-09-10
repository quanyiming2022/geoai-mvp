"""Real SSR access checks for project workspace; WebGL interaction verified in browser."""

import uuid
import httpx
from dotenv import dotenv_values
from migrate import ROOT


def run():
    env = dotenv_values(ROOT / ".env")
    api = "http://127.0.0.1:" + env["GEOAI_API_PORT"]
    web = "http://127.0.0.1:" + env["GEOAI_WEB_PORT"]
    key = env["SERVICE_ROLE_KEY"]
    for asset in ('maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs'):
        response = httpx.get(web + '/maplibre/' + asset, timeout=15).raise_for_status()
        assert 'javascript' in response.headers['content-type'] and len(response.content) > 1000
    ids = []
    with httpx.Client(
        base_url=env["SUPABASE_PUBLIC_URL"],
        headers={"apikey": key, "Authorization": "Bearer " + key},
        timeout=20,
    ) as admin:
        try:
            sessions = []
            for _ in range(2):
                seed = uuid.uuid4().hex
                credentials = {
                    "email": seed + "@example.test",
                    "password": seed + "Aa1!",
                }
                user = (
                    admin.post(
                        "/auth/v1/admin/users",
                        json={**credentials, "email_confirm": True},
                    )
                    .raise_for_status()
                    .json()
                )
                ids.append(user["id"])
                sessions.append(
                    httpx.post(api + "/auth/login", json=credentials, timeout=20)
                    .raise_for_status()
                    .json()
                )
            name = "Private workspace " + uuid.uuid4().hex
            project = (
                httpx.post(
                    api + "/projects",
                    headers={"Authorization": "Bearer " + sessions[0]["access_token"]},
                    json={"name": name},
                    timeout=20,
                )
                .raise_for_status()
                .json()
            )
            path = "/projects/" + project["id"] + "/workspace"
            for index in (0, 1):
                page = httpx.get(
                    web + path,
                    cookies={"geoai-access": sessions[index]["access_token"]},
                    timeout=30,
                )
                if index == 0:
                    assert (
                        page.status_code == 200
                        and name in page.text
                        and "离线坐标画布" in page.text
                    )
                else:
                    assert name not in page.text and (
                        "404" in page.text or page.status_code == 404
                    )
            page = httpx.get(web + path, timeout=30, follow_redirects=True)
            assert page.url.path == "/login" and name not in page.text
            print(
                "PASS: owner workspace SSR, cross-user denial, unauthenticated redirect"
            )
        finally:
            for uid in ids:
                admin.delete("/auth/v1/admin/users/" + uid).raise_for_status()


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL: " + type(exc).__name__ + " (secrets suppressed)")
        raise SystemExit(1) from None

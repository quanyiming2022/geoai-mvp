"""Real raster upload, private storage, checksum and RLS checks."""

import hashlib
import uuid
import time
import httpx
from dotenv import dotenv_values
from migrate import ROOT, connection
from make_fixture import make_fixture


def run():
    env = dotenv_values(ROOT / ".env")
    api = "http://127.0.0.1:" + env["GEOAI_API_PORT"]
    web = "http://127.0.0.1:" + env["GEOAI_WEB_PORT"]
    deadline = time.monotonic() + 90
    while True:
        try:
            httpx.get(api + "/health/ready", timeout=15).raise_for_status()
            httpx.get(web + "/login", timeout=15).raise_for_status()
            break
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    auth = env["SUPABASE_PUBLIC_URL"]
    make_fixture(ROOT / "artifacts/demo-geotiff.tif")
    payload = make_fixture(
        ROOT / "artifacts/large-geotiff.tif", dimension=2048, compress=None
    ).read_bytes()
    assert len(payload) > 10 * 1024 * 1024
    key = env["SERVICE_ROLE_KEY"]
    ids, assets = [], []
    with httpx.Client(
        base_url=auth,
        timeout=30,
        headers={"apikey": key, "Authorization": "Bearer " + key},
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
            with (
                httpx.Client(
                    base_url=api,
                    timeout=30,
                    headers={"Authorization": "Bearer " + sessions[0]["access_token"]},
                ) as a,
                httpx.Client(
                    base_url=api,
                    timeout=30,
                    headers={"Authorization": "Bearer " + sessions[1]["access_token"]},
                ) as b,
            ):
                project = (
                    a.post("/projects", json={"name": "P3 disposable"})
                    .raise_for_status()
                    .json()
                )
                path = "/projects/" + project["id"]
                assert (
                    a.post(
                        path + "/rasters",
                        content=b"<VRTDataset/>",
                        headers={"x-filename": "invalid.tif"},
                    ).status_code
                    == 422
                )
                assert (
                    b.post(
                        path + "/rasters",
                        content=payload,
                        headers={"x-filename": "demo.tif"},
                    ).status_code
                    == 404
                )
                a.post(
                    path + "/members", json={"user_id": ids[1], "role": "viewer"}
                ).raise_for_status()
                assert (
                    b.post(
                        path + "/rasters",
                        content=payload,
                        headers={"x-filename": "demo.tif"},
                    ).status_code
                    == 403
                )
                with httpx.Client(
                    base_url=web,
                    timeout=60,
                    cookies={
                        "geoai-access": "header.eyJleHAiOjB9.invalid",
                        "geoai-refresh": sessions[0]["refresh_token"],
                    },
                ) as bff:
                    assert (
                        bff.post(
                            "/api" + path + "/rasters",
                            content=payload,
                            headers={
                                "x-filename": "demo.tif",
                                "Origin": "https://evil.example",
                            },
                        ).status_code
                        == 403
                    )
                    asset = (
                        bff.post(
                            "/api" + path + "/rasters",
                            content=payload,
                            headers={"x-filename": "demo.tif", "Origin": web},
                        )
                        .raise_for_status()
                        .json()
                    )
                    assets.append(asset)
                assert asset["checksum"] == hashlib.sha256(payload).hexdigest()
                assert asset["size"] == len(payload) and asset["status"] == "uploaded"
                assert any(
                    row["id"] == asset["id"]
                    for row in b.get(path + "/rasters").raise_for_status().json()
                )
                signed = (
                    b.get("/rasters/" + asset["id"] + "/download")
                    .raise_for_status()
                    .json()["url"]
                )
                assert (
                    httpx.get(signed, timeout=30).raise_for_status().content == payload
                )
                assert (
                    httpx.get(
                        auth
                        + "/storage/v1/object/public/"
                        + asset["bucket"]
                        + "/"
                        + asset["object_key"],
                        timeout=20,
                    ).status_code
                    >= 400
                )
                with connection() as conn:
                    row = conn.execute(
                        "SELECT size,checksum FROM public.raster_assets WHERE id=%s",
                        (asset["id"],),
                    ).fetchone()
                    assert row == (len(payload), hashlib.sha256(payload).hexdigest())
                print(
                    "PASS: same-origin streamed upload, SHA256, SQL metadata, private Storage and viewer download",
                    flush=True,
                )
                direct = {
                    "apikey": env["ANON_KEY"],
                    "Authorization": "Bearer " + sessions[1]["access_token"],
                }
                forged = {
                    key: asset[key]
                    for key in (
                        "id",
                        "project_id",
                        "created_by",
                        "filename",
                        "bucket",
                        "object_key",
                        "size",
                        "checksum",
                    )
                }
                forged["id"] = str(uuid.uuid4())
                forged["created_by"] = ids[1]
                forged["object_key"] = (
                    project["id"] + "/rasters/" + forged["id"] + "/source.tif"
                )
                assert (
                    httpx.post(
                        auth + "/rest/v1/raster_assets",
                        headers=direct,
                        json=forged,
                        timeout=20,
                    ).status_code
                    == 403
                )
                a.delete(path + "/members/" + ids[1]).raise_for_status()
                assert b.get("/rasters/" + asset["id"] + "/download").status_code == 404
                assert (
                    httpx.get(
                        auth + "/rest/v1/raster_assets",
                        headers=direct,
                        params={"id": "eq." + asset["id"]},
                        timeout=20,
                    )
                    .raise_for_status()
                    .json()
                    == []
                )
                print(
                    "PASS: malformed TIFF, cross-project/viewer upload, Origin and direct RLS isolation",
                    flush=True,
                )
        finally:
            for asset in assets:
                admin.request(
                    "DELETE",
                    "/storage/v1/object/" + asset["bucket"],
                    json={"prefixes": [asset["object_key"]]},
                ).raise_for_status()
            # raster created_by intentionally restricts deleting an account while its assets exist.
            with connection() as conn:
                for asset in assets:
                    conn.execute(
                        "DELETE FROM public.raster_assets WHERE id=%s", (asset["id"],)
                    )
            for uid in ids:
                admin.delete("/auth/v1/admin/users/" + uid).raise_for_status()
    print(
        "PASS: P3 integration; generated fixture remains local for browser QA",
        flush=True,
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL: " + type(exc).__name__ + " (secrets suppressed)", flush=True)
        raise SystemExit(1) from None

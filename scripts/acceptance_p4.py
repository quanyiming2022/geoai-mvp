"""Live worker -> COG -> range read -> reprojected tile acceptance."""

import math
import time
import uuid
import httpx
from rasterio.io import MemoryFile
from dotenv import dotenv_values
from migrate import ROOT, connection
from make_fixture import make_fixture


def run():
    env = dotenv_values(ROOT / ".env")
    auth = env["SUPABASE_PUBLIC_URL"]
    api = "http://127.0.0.1:" + env["GEOAI_API_PORT"]
    web = "http://127.0.0.1:" + env["GEOAI_WEB_PORT"]
    deadline = time.monotonic() + 90
    while True:
        try:
            httpx.get(api + "/health/ready", timeout=15).raise_for_status()
            break
        except httpx.HTTPError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    key = env["SERVICE_ROLE_KEY"]
    users = []
    asset = None
    with httpx.Client(
        base_url=auth,
        headers={"apikey": key, "Authorization": "Bearer " + key},
        timeout=30,
    ) as admin:
        try:
            tokens = []
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
                users.append(user["id"])
                tokens.append(
                    httpx.post(api + "/auth/login", json=credentials, timeout=30)
                    .raise_for_status()
                    .json()["access_token"]
                )
            with httpx.Client(
                base_url=api,
                headers={"Authorization": "Bearer " + tokens[0]},
                timeout=60,
            ) as a:
                project = (
                    a.post("/projects", json={"name": "P4 disposable"})
                    .raise_for_status()
                    .json()
                )
                path = "/projects/" + project["id"]
                payload = make_fixture(ROOT / "artifacts/demo-geotiff.tif").read_bytes()
                asset = (
                    a.post(
                        path + "/rasters",
                        headers={"x-filename": "demo.tif"},
                        content=payload,
                    )
                    .raise_for_status()
                    .json()
                )
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    row = next(
                        v
                        for v in a.get(path + "/rasters").raise_for_status().json()
                        if v["id"] == asset["id"]
                    )
                    if row["status"] in ("ready", "failed"):
                        break
                    time.sleep(2)
                assert row["status"] == "ready", row.get("error_code")
                assert (row["width"], row["height"], row["bands"], row["crs"]) == (
                    256,
                    256,
                    3,
                    "EPSG:4326",
                )
                a.post(
                    path + "/members", json={"user_id": users[1], "role": "viewer"}
                ).raise_for_status()
                with connection() as conn:
                    conn.execute(
                        "UPDATE public.raster_assets SET status='failed',error_code='qa_retry_probe' WHERE id=%s",
                        (row["id"],),
                    )
                assert (
                    httpx.post(
                        api + "/rasters/" + row["id"] + "/retry",
                        headers={"Authorization": "Bearer " + tokens[1]},
                        timeout=30,
                    ).status_code
                    == 403
                )
                a.post("/rasters/" + row["id"] + "/retry").raise_for_status()
                a.delete(path + "/members/" + users[1]).raise_for_status()
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    row = next(
                        v
                        for v in a.get(path + "/rasters").raise_for_status().json()
                        if v["id"] == asset["id"]
                    )
                    if row["status"] in ("ready", "failed"):
                        break
                    time.sleep(1)
                assert row["status"] == "ready"
                print(
                    "PASS: owner retry, viewer denial and successful reprocessing",
                    flush=True,
                )
                cog = admin.get(
                    "/storage/v1/object/authenticated/"
                    + row["bucket"]
                    + "/"
                    + row["cog_object_key"]
                ).raise_for_status()
                with MemoryFile(cog.content) as memory, memory.open() as ds:
                    assert ds.tags(ns="IMAGE_STRUCTURE")["LAYOUT"] == "COG"
                    assert ds.crs.to_epsg() == 4326 and ds.block_shapes[0] == (512, 512)
                range_response = admin.get(
                    "/storage/v1/object/authenticated/"
                    + row["bucket"]
                    + "/"
                    + row["cog_object_key"],
                    headers={"Range": "bytes=0-255"},
                ).raise_for_status()
                assert (
                    range_response.status_code == 206
                    and len(range_response.content) == 256
                )
                thumb = admin.get(
                    "/storage/v1/object/authenticated/"
                    + row["bucket"]
                    + "/"
                    + row["thumbnail_object_key"]
                ).raise_for_status()
                assert thumb.content.startswith(b"\x89PNG")
                with connection() as conn:
                    geom = conn.execute(
                        "SELECT ST_SRID(footprint),ST_IsValid(footprint),ST_XMin(footprint),ST_YMax(footprint) FROM public.raster_assets WHERE id=%s",
                        (row["id"],),
                    ).fetchone()
                    assert (
                        geom[:2] == (4326, True)
                        and abs(geom[2] - 116.3) < 1e-6
                        and abs(geom[3] - 40) < 1e-6
                    )
                print(
                    "PASS: real worker COG/thumbnail, original CRS, PostGIS footprint, HTTP Range 206",
                    flush=True,
                )
                z = 14
                lng = (row["bbox"][0] + row["bbox"][2]) / 2
                lat = (row["bbox"][1] + row["bbox"][3]) / 2
                x = int((lng + 180) / 360 * 2**z)
                y = int(
                    (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**z
                )
                tile_path = f"/rasters/{row['id']}/tiles/{z}/{x}/{y}.png"
                png = a.get(tile_path).raise_for_status().content
                with MemoryFile(png) as memory, memory.open() as ds:
                    assert (
                        ds.count == 4
                        and ds.read(4).max() == 255
                        and ds.read(1).max() > 0
                    )
                outside = (
                    a.get(f"/rasters/{row['id']}/tiles/4/0/0.png")
                    .raise_for_status()
                    .content
                )
                with MemoryFile(outside) as memory, memory.open() as ds:
                    assert ds.read(4).max() == 0
                assert (
                    httpx.get(
                        api + tile_path,
                        headers={"Authorization": "Bearer " + tokens[1]},
                        timeout=30,
                    ).status_code
                    == 404
                )
                route = f"/api/rasters/{row['id']}/tiles/{z}/{x}/{y}"
                assert (
                    httpx.get(
                        web + route, cookies={"geoai-access": tokens[0]}, timeout=60
                    )
                    .raise_for_status()
                    .content.startswith(b"\x89PNG")
                )
                print(
                    "PASS: georeferenced nonempty tile, transparent outside tile, cross-user denial, Next tile proxy",
                    flush=True,
                )
        finally:
            if asset:
                prefix = f"{asset['project_id']}/rasters/{asset['id']}/"
                admin.request(
                    "DELETE",
                    "/storage/v1/object/" + asset["bucket"],
                    json={
                        "prefixes": [
                            prefix + name
                            for name in ("source.tif", "cog.tif", "thumbnail.png")
                        ]
                    },
                ).raise_for_status()
                with connection() as conn:
                    conn.execute(
                        "DELETE FROM public.raster_assets WHERE id=%s", (asset["id"],)
                    )
            for uid in users:
                admin.delete("/auth/v1/admin/users/" + uid).raise_for_status()
    print("PASS: P4 live integration", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL: " + type(exc).__name__ + " (secrets suppressed)", flush=True)
        raise SystemExit(1) from None

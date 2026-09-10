"""Real local acceptance. Nonzero on any failure; no implicit skips or secret output."""

import asyncio
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
import httpx
import psycopg
from redis import Redis
from dotenv import dotenv_values
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
from geoai.storage import SupabaseStorage  # noqa: E402


def run():
    infra_only = "--infrastructure-only" in sys.argv
    env = dotenv_values(ROOT / ".env")
    url = env["SUPABASE_PUBLIC_URL"]
    token = env["SERVICE_ROLE_KEY"]
    compose = ["sh", str(ROOT / "scripts/compose.sh")]

    def sql(query, params=None):
        with psycopg.connect(
            host="127.0.0.1",
            port=env["GEOAI_DB_PORT"],
            user="postgres",
            password=env["POSTGRES_PASSWORD"],
            dbname="postgres",
            connect_timeout=5,
        ) as c:
            return (
                c.execute(query, params).fetchall()
                if query.lstrip().upper().startswith("SELECT")
                else c.execute(query, params)
            )

    def containers():
        ids = subprocess.check_output(compose + ["ps", "-q"], text=True).split()
        if not ids:
            raise RuntimeError("No containers running")
        # Inspect only state, never Config.Env (contains secrets).
        for cid in ids:
            state = json.loads(
                subprocess.check_output(
                    ["docker", "inspect", "--format", "{{json .State}}", cid], text=True
                )
            )
            if (
                not state["Running"]
                or state.get("Health", {}).get("Status", "healthy") != "healthy"
            ):
                raise RuntimeError("Container unhealthy")
        if len(ids) < (11 if infra_only else 14):
            raise RuntimeError("Required services missing")

    def wait_healthy():
        deadline = time.monotonic() + 120
        while True:
            try:
                containers()
                return
            except RuntimeError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)

    wait_healthy()
    print("PASS: container states", flush=True)
    versions = sql("SELECT version(), PostGIS_Version()")
    assert versions[0][0] and versions[0][1]
    print("PASS: PostgreSQL and PostGIS SQL", flush=True)
    redis = Redis(host="127.0.0.1", port=int(env["GEOAI_REDIS_PORT"]), socket_timeout=5)
    assert redis.ping()
    if not infra_only:
        assert redis.exists("geoai:raster:heartbeat")
    print(
        "PASS: Redis PING" + ("" if infra_only else " and Raster heartbeat"), flush=True
    )
    storage = SupabaseStorage(url, token)
    uid = uuid.uuid4().hex
    key = "p0-probes/" + uid + ".bin"
    payload = b"GeoAI persistence " + uid.encode()
    with httpx.Client(
        timeout=15, headers={"apikey": token, "Authorization": "Bearer " + token}
    ) as http:
        bucket = http.post(
            url + "/storage/v1/bucket",
            json={
                "id": env["STORAGE_BUCKET"],
                "name": env["STORAGE_BUCKET"],
                "public": False,
            },
        )
        if bucket.status_code not in (200, 201, 409):
            # Existing bucket must be verified, not silently ignore an arbitrary error.
            http.get(
                url + "/storage/v1/bucket/" + env["STORAGE_BUCKET"]
            ).raise_for_status()
        http.get(url + "/rest/v1/").raise_for_status()
        http.get(url + "/auth/v1/health").raise_for_status()
        print("PASS: PostgREST and Auth health", flush=True)
        user = (
            http.post(
                url + "/auth/v1/admin/users",
                json={
                    "email": uid + "@example.test",
                    "password": uid + "Aa1!",
                    "email_confirm": True,
                },
            )
            .raise_for_status()
            .json()
        )
        try:
            with httpx.Client(timeout=15, headers={"apikey": env["ANON_KEY"]}) as anon:
                login = (
                    anon.post(
                        url + "/auth/v1/token?grant_type=password",
                        json={"email": uid + "@example.test", "password": uid + "Aa1!"},
                    )
                    .raise_for_status()
                    .json()
                )
                me = (
                    anon.get(
                        url + "/auth/v1/user",
                        headers={"Authorization": "Bearer " + login["access_token"]},
                    )
                    .raise_for_status()
                    .json()
                )
                assert me["id"] == user["id"]
            print("PASS: Auth create/login/get-user", flush=True)
        finally:
            http.delete(url + "/auth/v1/admin/users/" + user["id"]).raise_for_status()

    async def realtime():
        wsurl = url.replace("http://", "ws://").replace("https://", "wss://")
        async with connect(
            wsurl + "/realtime/v1/websocket?apikey=" + env["ANON_KEY"] + "&vsn=1.0.0",
            open_timeout=10,
            proxy=None,
        ) as ws:
            await ws.send(
                json.dumps(
                    {
                        "topic": "phoenix",
                        "event": "heartbeat",
                        "payload": {},
                        "ref": "1",
                    }
                )
            )
            reply = json.loads(await asyncio.wait_for(ws.recv(), 10))
            assert reply["event"] == "phx_reply" and reply["payload"]["status"] == "ok"

    asyncio.run(realtime())
    print("PASS: Realtime WebSocket heartbeat", flush=True)
    storage.put_object(env["STORAGE_BUCKET"], key, payload, "application/octet-stream")
    assert storage.exists(env["STORAGE_BUCKET"], key)
    assert storage.get_object(env["STORAGE_BUCKET"], key) == payload
    assert storage.head_object(env["STORAGE_BUCKET"], key)["size"] == len(payload)
    signed = storage.create_signed_url(env["STORAGE_BUCKET"], key)
    assert httpx.get(signed, timeout=10).raise_for_status().content == payload
    print("PASS: Storage upload/download/head/signed URL", flush=True)
    sql(
        "INSERT INTO geoai_internal.persistence_probe (id,value) VALUES (%s,%s)",
        (uid, uid),
    )
    redis.set("geoai:persistence:" + uid, uid)
    time.sleep(2)  # Redis appendfsync everysec
    subprocess.run(
        compose + ["restart", "db", "storage", "redis"],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    for attempt in range(60):
        try:
            assert (
                sql(
                    "SELECT value FROM geoai_internal.persistence_probe WHERE id=%s",
                    (uid,),
                )[0][0]
                == uid
            )
            assert redis.get("geoai:persistence:" + uid) == uid.encode()
            assert storage.get_object(env["STORAGE_BUCKET"], key) == payload
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)
    print("PASS: database/storage/Redis restart persistence", flush=True)
    storage.delete_object(env["STORAGE_BUCKET"], key)
    assert not storage.exists(env["STORAGE_BUCKET"], key)
    sql("DELETE FROM geoai_internal.persistence_probe WHERE id=%s", (uid,))
    redis.delete("geoai:persistence:" + uid)
    storage.close()
    redis.close()
    wait_healthy()
    if infra_only:
        containers()
        print(
            "PASS: infrastructure subset only; API/Web/Raster and full P0 remain unverified"
        )
        return
    for name, endpoint in [
        ("FastAPI", "http://127.0.0.1:" + env["GEOAI_API_PORT"] + "/health/ready"),
        ("Web", "http://127.0.0.1:" + env["GEOAI_WEB_PORT"] + "/"),
        ("Web to FastAPI", "http://127.0.0.1:" + env["GEOAI_WEB_PORT"] + "/api/health"),
    ]:
        deadline = time.monotonic() + 90
        while True:
            try:
                response = httpx.get(endpoint, timeout=15, follow_redirects=True).raise_for_status()
                if name != "Web":
                    payload = response.json()
                    required = {
                        "postgresql_postgis",
                        "redis",
                        "raster_worker",
                        "auth",
                        "postgrest",
                        "storage",
                        "realtime",
                        "compute_provider",
                        "model_adapter",
                    }
                    assert payload["status"] == "ok"
                    assert required <= payload["checks"].keys()
                    assert all(value == "ok" for value in payload["checks"].values())
                break
            except (httpx.HTTPError, AssertionError, KeyError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(2)
        print("PASS: " + name, flush=True)
    containers()
    print(
        "PASS: integration acceptance. Browser and build checks are separate requirements."
    )


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(
            "FAIL: "
            + type(exc).__name__
            + " (inspect local service status; secrets suppressed)",
            flush=True,
        )
        sys.exit(1)

import json
from websockets.sync.client import connect
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import psycopg
from redis import Redis
from .config import Settings
from .models import MockAdapter
from .compute import MockComputeProvider

from .auth import router as auth_router
from .projects import router as projects_router
from .rasters import router as rasters_router

app = FastAPI(title="GeoAI Platform", version="0.1.0")
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(rasters_router)


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health/live")
def live():
    return {"status": "ok", "phase": "P0"}


@app.get("/health/ready")
def ready():
    checks = {}
    try:
        cfg = Settings()
    except Exception:
        return JSONResponse(
            {"status": "unavailable", "checks": {"configuration": "invalid"}}, status_code=503
        )

    def check(name, fn):
        try:
            fn()
            checks[name] = "ok"
        except Exception as exc:
            # Never put connection strings, JWTs or exception messages in public health output.
            checks[name] = type(exc).__name__

    def database():
        with psycopg.connect(cfg.database_url.get_secret_value(), connect_timeout=3) as conn:
            conn.execute("SELECT version(), PostGIS_Version()").fetchone()

    check("postgresql_postgis", database)
    client = Redis.from_url(
        cfg.redis_url.get_secret_value(), socket_timeout=3, socket_connect_timeout=3
    )
    check("redis", client.ping)

    def worker():
        if not client.exists("geoai:raster:heartbeat"):
            raise RuntimeError("Raster worker heartbeat expired")

    check("raster_worker", worker)
    client.close()
    with httpx.Client(
        timeout=5,
        headers={
            "apikey": cfg.service_role_key.get_secret_value(),
            "Authorization": "Bearer " + cfg.service_role_key.get_secret_value(),
        },
    ) as http:
        for name, path in [
            ("auth", "/auth/v1/health"),
            ("postgrest", "/rest/v1/"),
            ("storage", "/storage/v1/bucket"),
        ]:
            check(name, lambda p=path: http.get(cfg.supabase_url + p).raise_for_status())

    def realtime():
        ws_url = cfg.supabase_url.replace("http://", "ws://").replace("https://", "wss://")
        with connect(
            ws_url
            + "/realtime/v1/websocket?apikey="
            + cfg.anon_key.get_secret_value()
            + "&vsn=1.0.0",
            open_timeout=3,
            proxy=None,
            close_timeout=1,
        ) as ws:
            ws.send(
                json.dumps({"topic": "phoenix", "event": "heartbeat", "payload": {}, "ref": "1"})
            )
            reply = json.loads(ws.recv(timeout=3))
            if reply.get("payload", {}).get("status") != "ok":
                raise RuntimeError("Realtime heartbeat failed")

    check("realtime", realtime)
    check("compute_provider", lambda: MockComputeProvider(MockAdapter()).healthcheck())
    check("model_adapter", lambda: MockAdapter().healthcheck())
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks}, status_code=200 if ok else 503
    )

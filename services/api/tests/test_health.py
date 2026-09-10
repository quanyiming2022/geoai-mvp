from fastapi.testclient import TestClient
from geoai.main import app


def test_live_is_not_readiness():
    client = TestClient(app)
    assert client.get("/health/live").json() == {"status": "ok", "phase": "P0"}


def test_unconfigured_readiness_fails_closed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in [
        "DATABASE_URL",
        "REDIS_URL",
        "SUPABASE_URL",
        "SUPABASE_PUBLIC_URL",
        "SERVICE_ROLE_KEY",
        "ANON_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)
    result = TestClient(app).get("/health/ready")
    assert result.status_code == 503
    assert result.json()["checks"]["configuration"] == "invalid"

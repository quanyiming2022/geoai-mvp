import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from geoai.main import app
from geoai.projects import ProjectInput, MemberInput


def test_project_name_and_extra_fields():
    for data in [{"name": "   "}, {"name": "x", "owner_id": "spoof"}, {"name": "x" * 121}]:
        with pytest.raises(ValidationError):
            ProjectInput(**data)
    assert ProjectInput(name="  A  ").name == "A"


def test_member_cannot_promote_owner():
    with pytest.raises(ValidationError):
        MemberInput(user_id="00000000-0000-0000-0000-000000000001", role="owner")


def test_projects_require_authentication():
    assert TestClient(app).get("/projects").status_code == 401


def test_auth_outage_preserves_retryable_status(monkeypatch):
    from geoai import auth
    from fastapi import HTTPException
    import httpx

    class Key:
        def get_secret_value(self):
            return "test"

    class Config:
        anon_key = Key()
        supabase_url = "http://test"

    monkeypatch.setattr(auth, "Settings", Config)
    monkeypatch.setattr(auth.httpx, "request", lambda *a, **kw: httpx.Response(503))
    with pytest.raises(HTTPException) as error:
        auth.auth_request("POST", "token?grant_type=refresh_token")
    assert error.value.status_code == 503

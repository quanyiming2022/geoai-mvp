from dataclasses import dataclass
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
import httpx
from .config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=128)


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=4096)


def auth_request(method, path, token=None, body=None):
    cfg = Settings()
    headers = {"apikey": cfg.anon_key.get_secret_value()}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        response = httpx.request(
            method, cfg.supabase_url + "/auth/v1/" + path, headers=headers, json=body, timeout=15
        )
    except httpx.HTTPError:
        raise HTTPException(503, "Authentication service unavailable") from None
    if response.status_code >= 500:
        raise HTTPException(503, "Authentication service unavailable")
    if response.status_code >= 400:
        code = 429 if response.status_code == 429 else 401
        raise HTTPException(code, "Authentication failed" if code == 401 else "Try again later")
    return response.json() if response.content else {}


def session(data):
    if not data.get("access_token"):
        return {"confirmation_required": True}
    return {key: data[key] for key in ("access_token", "refresh_token", "expires_in", "user")}


@router.post("/login")
def login(data: Credentials):
    return session(auth_request("POST", "token?grant_type=password", body=data.model_dump()))


@router.post("/signup")
def signup(data: Credentials):
    return session(auth_request("POST", "signup", body=data.model_dump()))


@router.post("/refresh")
def refresh(data: RefreshInput):
    return session(auth_request("POST", "token?grant_type=refresh_token", body=data.model_dump()))


@dataclass
class Identity:
    token: str
    user: dict


def identity(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None:
        raise HTTPException(401, "Sign in required")
    user = auth_request("GET", "user", token=credentials.credentials)
    if not user.get("id") or user.get("is_anonymous"):
        raise HTTPException(401, "Account required")
    return Identity(credentials.credentials, user)


CurrentUser = Annotated[Identity, Depends(identity)]


@router.get("/me")
def me(current: CurrentUser):
    return {"id": current.user["id"], "email": current.user.get("email")}


@router.post("/logout", status_code=204)
def logout(current: CurrentUser):
    auth_request("POST", "logout?scope=local", token=current.token)

from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .auth import CurrentUser
from .postgrest import PostgrestProjectRepository

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Name required")
        return value.strip()


class RoleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["editor", "viewer"]


class MemberInput(RoleInput):
    user_id: UUID


def accessible(project_id, current):
    repo = PostgrestProjectRepository(current.token)
    project = repo.get(project_id, current.user["id"])
    if project is None:
        raise HTTPException(404, "Project not found")
    return repo, project


@router.get("")
def projects(current: CurrentUser):
    return PostgrestProjectRepository(current.token).list_for_user(current.user["id"])


@router.post("", status_code=201)
def create(data: ProjectInput, current: CurrentUser):
    return PostgrestProjectRepository(current.token).create(data.model_dump(), current.user["id"])


@router.get("/{project_id}")
def project(project_id: UUID, current: CurrentUser):
    repo, row = accessible(project_id, current)
    members = repo.members(project_id)
    role = (
        "owner"
        if row["owner_id"] == current.user["id"]
        else next((m["role"] for m in members if m["user_id"] == current.user["id"]), "viewer")
    )
    return {**row, "members": members, "my_role": role}


@router.patch("/{project_id}")
def update(project_id: UUID, data: ProjectInput, current: CurrentUser):
    repo, _ = accessible(project_id, current)
    return repo.update(project_id, data.model_dump())


@router.post("/{project_id}/members", status_code=201)
def add_member(project_id: UUID, data: MemberInput, current: CurrentUser):
    repo, row = accessible(project_id, current)
    if row["owner_id"] != current.user["id"] or str(data.user_id) == row["owner_id"]:
        raise HTTPException(403, "Only owners can manage non-owner members")
    return repo.add_member(project_id, data.model_dump(mode="json"))


@router.patch("/{project_id}/members/{user_id}")
def change_member(project_id: UUID, user_id: UUID, data: RoleInput, current: CurrentUser):
    repo, row = accessible(project_id, current)
    if row["owner_id"] != current.user["id"]:
        raise HTTPException(403, "Only owners can manage members")
    return repo.change_member(project_id, user_id, data.role)


@router.delete("/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: UUID, user_id: UUID, current: CurrentUser):
    repo, row = accessible(project_id, current)
    if row["owner_id"] != current.user["id"]:
        raise HTTPException(403, "Only owners can manage members")
    repo.remove_member(project_id, user_id)


class EmailMemberInput(RoleInput):
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def member_identities(ids):
    # Only invoked after project access has been checked; never a public directory.
    import psycopg
    from .config import Settings
    with psycopg.connect(Settings().database_url.get_secret_value(), connect_timeout=5) as conn:
        rows = conn.execute("SELECT id, email FROM auth.users WHERE id = ANY(%s::uuid[])", (list(ids),)).fetchall()
    return {str(uid): email for uid, email in rows}


@router.get("/{project_id}/member-identities")
def project_member_identities(project_id: UUID, current: CurrentUser):
    repo, row = accessible(project_id, current)
    members = [{"user_id": row["owner_id"], "role": "owner"}, *repo.members(project_id)]
    emails = member_identities([m["user_id"] for m in members])
    return [{"user_id": m["user_id"], "role": m["role"], "email": emails.get(m["user_id"]), "status": "active"} for m in members]


@router.post("/{project_id}/members/by-email", status_code=201)
def add_member_by_email(project_id: UUID, data: EmailMemberInput, current: CurrentUser):
    repo, row = accessible(project_id, current)
    if row["owner_id"] != current.user["id"]:
        raise HTTPException(403, "Only owners can manage members")
    import psycopg
    from .config import Settings
    with psycopg.connect(Settings().database_url.get_secret_value(), connect_timeout=5) as conn:
        users = conn.execute("SELECT id FROM auth.users WHERE lower(email) = lower(%s) AND deleted_at IS NULL LIMIT 2", (data.email.strip(),)).fetchall()
    if len(users) != 1:
        raise HTTPException(404, "Account not found")
    uid = str(users[0][0])
    if uid == row["owner_id"]:
        raise HTTPException(409, "Owner is already a member")
    return repo.add_member(project_id, {"user_id": uid, "role": data.role})

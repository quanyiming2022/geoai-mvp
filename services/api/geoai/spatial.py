"""Authenticated PostGIS repositories. RLS remains enforced even over SQL."""

import json
import math
from typing import Literal
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .auth import CurrentUser
from .config import Settings
from .projects import accessible


class PolygonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["Polygon"]
    coordinates: list[list[list[float]]]

    @field_validator("coordinates")
    @classmethod
    def valid_coordinates(cls, rings):
        if not rings or sum(len(r) for r in rings) > 1000:
            raise ValueError("Invalid vertex count")
        for ring in rings:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError("Ring must be closed")
            for point in ring:
                if (
                    len(point) != 2
                    or not all(math.isfinite(v) for v in point)
                    or not (-180 <= point[0] <= 180 and -85.0511 <= point[1] <= 85.0511)
                ):
                    raise ValueError("Invalid WGS84 coordinates")
        longitudes = [p[0] for ring in rings for p in ring]
        if max(longitudes) - min(longitudes) > 180:
            raise ValueError("Antimeridian AOIs are not supported")
        return rings


class AoiInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    geometry: PolygonInput
    description: str = Field(default="", max_length=2000)


class ResourceRevision(BaseModel):
    expected_revision: int = Field(ge=1, strict=True)


class AoiEditInput(AoiInput, ResourceRevision):
    pass


class RenameInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    expected_name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    expected_description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def paired_description(self):
        if (self.description is None) != (self.expected_description is None):
            raise ValueError("Description and previous value required together")
        return self


class UserSQLRepository:
    def __init__(self, user_id):
        self.user_id = str(UUID(str(user_id)))

    def execute(self, query, params=()):
        cfg = Settings()
        try:
            with psycopg.connect(
                cfg.database_url.get_secret_value(), connect_timeout=5, row_factory=dict_row
            ) as conn:
                conn.execute("SET LOCAL ROLE authenticated")
                conn.execute(
                    "SELECT set_config('request.jwt.claims',%s,true)",
                    (json.dumps({"sub": self.user_id, "role": "authenticated"}),),
                )
                conn.execute("SET LOCAL statement_timeout='15s'")
                return conn.execute(query, params).fetchall()
        except psycopg.errors.InsufficientPrivilege:
            raise HTTPException(403, "Permission denied") from None
        except (psycopg.IntegrityError, psycopg.DataError):
            raise HTTPException(422, "Invalid geometry or project reference") from None
        except psycopg.Error:
            raise HTTPException(503, "Spatial data service unavailable") from None


    def rename(self, kind, project_id, resource_id, data):
        # Identifiers are selected internally, never interpolated from a request.
        table = {"aoi": "aois", "prompt": "visual_prompts"}[kind]
        roles = self.execute(
            "SELECT geoai_internal.project_role(%s) AS role", (project_id,)
        )
        if not roles or roles[0]["role"] not in ("owner", "editor"):
            raise HTTPException(403, "Editor access required")
        if data.description is None:
            rows = self.execute(
                f"UPDATE public.{table} SET name=%s WHERE id=%s AND project_id=%s AND deleted_at IS NULL AND name=%s RETURNING id,name,description",
                (data.name, resource_id, project_id, data.expected_name),
            )
        else:
            rows = self.execute(
                f"UPDATE public.{table} SET name=%s,description=%s WHERE id=%s AND project_id=%s AND deleted_at IS NULL AND name=%s AND description=%s RETURNING id,name,description",
                (data.name, data.description, resource_id, project_id, data.expected_name, data.expected_description),
            )
        if rows:
            return rows[0]
        visible = self.execute(
            f"SELECT id FROM public.{table} WHERE id=%s AND project_id=%s",
            (resource_id, project_id),
        )
        if not visible:
            raise HTTPException(404, "Object not found")
        raise HTTPException(409, "Object changed; refresh before retrying")


class PostgisAoiRepository(UserSQLRepository):
    columns = "revision,updated_at,updated_by,id,project_id,name,description,created_by,created_at,extensions.ST_AsGeoJSON(geometry,17)::json AS geometry,extensions.ST_Area(geometry::extensions.geography) AS area_m2"

    def list_for_project(self, project_id, user_id):
        return self.execute(
            f"SELECT {self.columns} FROM public.aois WHERE project_id=%s AND deleted_at IS NULL ORDER BY created_at DESC",
            (project_id,),
        )

    def get(self, resource_id, user_id):
        rows = self.execute(f"SELECT {self.columns} FROM public.aois WHERE id=%s AND deleted_at IS NULL", (resource_id,))
        return rows[0] if rows else None

    def create(self, project_id, data):
        return self.execute(
            f"INSERT INTO public.aois(project_id,created_by,name,description,geometry) VALUES (%s,%s,%s,%s,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)) RETURNING {self.columns}",
            (project_id, self.user_id, data.name, data.description, data.geometry.model_dump_json()),
        )[0]


router = APIRouter(tags=["aois"])


@router.get("/projects/{project_id}/aois")
def list_aois(project_id: UUID, current: CurrentUser):
    accessible(project_id, current)
    return PostgisAoiRepository(current.user["id"]).list_for_project(project_id, current.user["id"])


@router.post("/projects/{project_id}/aois", status_code=201)
def create_aoi(project_id: UUID, data: AoiInput, current: CurrentUser):
    accessible(project_id, current)
    return PostgisAoiRepository(current.user["id"]).create(project_id, data)


@router.patch("/projects/{project_id}/aois/{resource_id}")
def rename_aoi(project_id: UUID, resource_id: UUID, data: RenameInput, current: CurrentUser):
    accessible(project_id, current)
    return UserSQLRepository(current.user["id"]).rename("aoi", project_id, resource_id, data)


def require_resource_editor(repo, project_id):
    rows=repo.execute('SELECT geoai_internal.project_role(%s) AS role',(project_id,))
    if not rows or rows[0]['role'] not in ('owner','editor'):
        raise HTTPException(403,'Editor access required')


def delete_resource(repo,kind,project_id,resource_id,revision):
    table={'aois':'aois','prompts':'visual_prompts'}[kind]
    require_resource_editor(repo,project_id)
    rows=repo.execute(f"UPDATE public.{table} SET deleted_at=now() WHERE id=%s AND project_id=%s AND revision=%s AND deleted_at IS NULL RETURNING id",(resource_id,project_id,revision))
    if not rows:raise HTTPException(409,'Resource changed or deleted; refresh before retrying')
    return {'deleted':str(rows[0]['id'])}


@router.put('/projects/{project_id}/aois/{resource_id}')
def edit_aoi(project_id:UUID,resource_id:UUID,data:AoiEditInput,current:CurrentUser):
    accessible(project_id,current)
    repo=PostgisAoiRepository(current.user['id'])
    require_resource_editor(repo,project_id)
    rows=repo.execute(f"UPDATE public.aois SET name=%s,description=%s,geometry=extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326) WHERE id=%s AND project_id=%s AND revision=%s AND deleted_at IS NULL RETURNING {repo.columns}",(data.name,data.description,data.geometry.model_dump_json(),resource_id,project_id,data.expected_revision))
    if not rows:raise HTTPException(409,'AOI changed or deleted; refresh before retrying')
    return rows[0]


@router.delete('/projects/{project_id}/aois/{resource_id}')
def delete_aoi(project_id:UUID,resource_id:UUID,data:ResourceRevision,current:CurrentUser):
    accessible(project_id,current)
    return delete_resource(UserSQLRepository(current.user['id']),'aois',project_id,resource_id,data.expected_revision)

"""Authenticated PostGIS repositories. RLS remains enforced even over SQL."""

import json
import math
from typing import Literal
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class PostgisAoiRepository(UserSQLRepository):
    columns = "id,project_id,name,created_by,created_at,extensions.ST_AsGeoJSON(geometry)::json AS geometry,extensions.ST_Area(geometry::extensions.geography) AS area_m2"

    def list_for_project(self, project_id, user_id):
        return self.execute(
            f"SELECT {self.columns} FROM public.aois WHERE project_id=%s ORDER BY created_at DESC",
            (project_id,),
        )

    def get(self, resource_id, user_id):
        rows = self.execute(f"SELECT {self.columns} FROM public.aois WHERE id=%s", (resource_id,))
        return rows[0] if rows else None

    def create(self, project_id, data):
        return self.execute(
            f"INSERT INTO public.aois(project_id,created_by,name,geometry) VALUES (%s,%s,%s,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)) RETURNING {self.columns}",
            (project_id, self.user_id, data.name, data.geometry.model_dump_json()),
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

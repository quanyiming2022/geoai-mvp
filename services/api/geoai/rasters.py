"""Bounded streaming upload; bytes stay on disk/object storage, never in Postgres."""

import asyncio
import hashlib
import os
import tempfile
from urllib.parse import unquote
from uuid import UUID, uuid4
import httpx
import rasterio
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from .auth import CurrentUser
from .config import Settings
from .postgrest import PostgrestRasterRepository
from .projects import accessible
from .storage import SupabaseStorage

router = APIRouter(tags=["rasters"])
upload_slots = asyncio.Semaphore(2)


def safe_filename(value):
    name = unquote(value)
    if (
        not name
        or len(name) > 255
        or any(ord(c) < 32 for c in name)
        or "/" in name
        or "\\" in name
        or not name.lower().endswith((".tif", ".tiff"))
    ):
        raise HTTPException(422, "A plain .tif or .tiff filename is required")
    return name


def validate_header(header):
    if header[:4] not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
        raise HTTPException(422, "Only GeoTIFF data is accepted")


def validate_raster(path):
    try:
        with rasterio.open(path, driver="GTiff") as dataset:
            if dataset.crs is None or dataset.width < 1 or dataset.height < 1:
                raise HTTPException(422, "GeoTIFF must have a CRS and valid dimensions")
    except rasterio.errors.RasterioError:
        raise HTTPException(422, "Invalid GeoTIFF") from None


def provider(cfg):
    return SupabaseStorage(
        cfg.supabase_url,
        cfg.service_role_key.get_secret_value(),
        public_url=cfg.supabase_public_url,
    )


def persist(path, filename, size, checksum, project_id, current, cfg):
    validate_raster(path)
    asset_id = str(uuid4())
    key = f"{project_id}/rasters/{asset_id}/source.tif"
    storage = provider(cfg)
    try:
        with open(path, "rb") as source:
            storage.put_object(cfg.storage_bucket, key, source, "image/tiff")
        try:
            return PostgrestRasterRepository(current.token).create(
                {
                    "id": asset_id,
                    "project_id": str(project_id),
                    "created_by": current.user["id"],
                    "filename": filename,
                    "bucket": cfg.storage_bucket,
                    "object_key": key,
                    "size": size,
                    "checksum": checksum,
                }
            )
        except HTTPException as error:
            if error.status_code < 500:
                # A definitive Data API rejection means the row did not commit.
                storage.delete_object(cfg.storage_bucket, key)
                raise
            # An interrupted response can follow a committed INSERT. Never delete
            # that source. Reconcile through the same user's RLS-scoped repository.
            try:
                row = PostgrestRasterRepository(current.token).get(asset_id, current.user["id"])
                if row and row["checksum"] == checksum and row["object_key"] == key:
                    return row
            except HTTPException:
                pass
            raise HTTPException(
                503, {"code": "registration_uncertain", "asset_id": asset_id}
            ) from None
    except httpx.HTTPError:
        raise HTTPException(503, "Object storage unavailable") from None
    finally:
        storage.close()


@router.get("/projects/{project_id}/rasters")
def list_rasters(project_id: UUID, current: CurrentUser):
    accessible(project_id, current)
    return PostgrestRasterRepository(current.token).list_for_project(project_id, current.user["id"])


@router.post("/projects/{project_id}/rasters", status_code=201)
async def upload(project_id: UUID, request: Request, current: CurrentUser):
    repo, project = await run_in_threadpool(accessible, project_id, current)
    members = await run_in_threadpool(repo.members, project_id)
    editor = project["owner_id"] == current.user["id"] or any(
        m["user_id"] == current.user["id"] and m["role"] == "editor" for m in members
    )
    if not editor:
        raise HTTPException(403, "Upload requires editor access")
    filename = safe_filename(request.headers.get("x-filename", ""))
    cfg = Settings()
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > cfg.max_upload_bytes:
                raise HTTPException(413, "Upload exceeds configured limit")
        except ValueError:
            raise HTTPException(400, "Invalid Content-Length") from None
    async with upload_slots:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as target:
            path = target.name
        try:
            size = 0
            digest = hashlib.sha256()
            prefix = b""
            with open(path, "wb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > cfg.max_upload_bytes:
                        raise HTTPException(413, "Upload exceeds configured limit")
                    if len(prefix) < 4:
                        prefix += chunk[: 4 - len(prefix)]
                        if len(prefix) == 4:
                            validate_header(prefix)
                    digest.update(chunk)
                    await run_in_threadpool(target.write, chunk)
            validate_header(prefix)
            return await run_in_threadpool(
                persist, path, filename, size, digest.hexdigest(), project_id, current, cfg
            )
        finally:
            os.unlink(path)


def asset_for_user(asset_id, current):
    row = PostgrestRasterRepository(current.token).get(asset_id, current.user["id"])
    if row is None:
        raise HTTPException(404, "Raster not found")
    cfg = Settings()
    canonical = f"{row['project_id']}/rasters/{row['id']}/source.tif"
    if row["object_key"] != canonical or row["bucket"] != cfg.storage_bucket:
        raise HTTPException(409, "Invalid asset storage reference")
    return row, cfg


@router.get("/rasters/{asset_id}/download")
def download(asset_id: UUID, current: CurrentUser):
    row, cfg = asset_for_user(asset_id, current)
    storage = provider(cfg)
    try:
        return {"url": storage.create_signed_url(cfg.storage_bucket, row["object_key"], 60)}
    except httpx.HTTPError:
        raise HTTPException(503, "Object storage unavailable") from None
    finally:
        storage.close()

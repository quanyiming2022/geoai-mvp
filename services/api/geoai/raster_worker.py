"""Durable raster claims and isolated conversion. Only internal worker uses DB admin."""

import hashlib
from pathlib import Path
from contextlib import nullcontext
import tempfile
from uuid import uuid4
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .config import Settings
from .rasters import provider
from .raster_processing import convert


def database(cfg):
    return psycopg.connect(
        cfg.database_url.get_secret_value(), connect_timeout=5, row_factory=dict_row, options="-c statement_timeout=15000 -c lock_timeout=5000"
    )


def claim(cfg):
    with database(cfg) as conn:
        conn.execute(
            "UPDATE public.raster_assets SET status='failed', error_code='worker_interrupted', finished_at=now() WHERE status='processing' AND started_at < now() - make_interval(secs => %s)",
            (cfg.raster_timeout_seconds + 30,),
        )
        row = conn.execute(
            "SELECT * FROM public.raster_assets WHERE status='uploaded' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if row:
            token = uuid4()
            conn.execute(
                "UPDATE public.raster_assets SET status='processing', processing_token=%s, started_at=now(), error_code=NULL WHERE id=%s",
                (token, row["id"]),
            )
            row["processing_token"] = token
        return row


def fail(cfg, row, code):
    with database(cfg) as conn:
        conn.execute(
            "UPDATE public.raster_assets SET status='failed', error_code=%s, finished_at=now() WHERE id=%s AND processing_token=%s AND status='processing'",
            (code, row["id"], row["processing_token"]),
        )


def process(row, workspace=None):
    cfg = Settings()
    storage = provider(cfg)
    try:
        prefix = f"{row['project_id']}/rasters/{row['id']}/"
        if row["bucket"] != cfg.storage_bucket or row["object_key"] != prefix + "source.tif":
            raise ValueError("invalid_storage_reference")
        with (
            nullcontext(workspace)
            if workspace
            else tempfile.TemporaryDirectory(prefix="geoai-raster-")
        ) as directory:
            source, cog, thumb = [
                Path(directory) / name for name in ("source.tif", "cog.tif", "thumbnail.png")
            ]
            storage.download_to_file(cfg.storage_bucket, row["object_key"], source)
            with open(source, "rb") as data:
                checksum = hashlib.file_digest(data, "sha256").hexdigest()
            if checksum != row["checksum"] or source.stat().st_size != row["size"]:
                raise ValueError("source_checksum_mismatch")
            meta = convert(source, cog, thumb, cfg.max_raster_pixels)
            for path, mime in ((cog, "image/tiff"), (thumb, "image/png")):
                with open(path, "rb") as data:
                    storage.put_object(cfg.storage_bucket, prefix + path.name, data, mime)
            with database(cfg) as conn:
                conn.execute(
                    """UPDATE public.raster_assets SET status='ready', width=%s,height=%s,bands=%s,dtype=%s,nodata=%s,crs=%s,resolution=%s,bbox=%s,
                footprint=extensions.ST_MakeEnvelope(%s,%s,%s,%s,4326),cog_object_key=%s,thumbnail_object_key=%s,display_ranges=%s,finished_at=now()
                WHERE id=%s AND processing_token=%s AND status='processing'""",
                    (
                        *[
                            meta[k]
                            for k in (
                                "width",
                                "height",
                                "bands",
                                "dtype",
                                "nodata",
                                "crs",
                                "resolution",
                                "bbox",
                            )
                        ],
                        *meta["bbox"],
                        prefix + "cog.tif",
                        prefix + "thumbnail.png",
                        Jsonb(meta["display_ranges"]),
                        row["id"],
                        row["processing_token"],
                    ),
                )
    except Exception as error:
        code = (
            str(error)
            if isinstance(error, ValueError)
            and str(error)
            in (
                "invalid_storage_reference",
                "source_checksum_mismatch",
                "invalid_crs_or_pixel_limit",
                "unsupported_geographic_extent",
            )
            else type(error).__name__
        )
        fail(cfg, row, code)
    finally:
        storage.close()

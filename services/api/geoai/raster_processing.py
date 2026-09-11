import math
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.enums import Resampling, ColorInterp
from rasterio.shutil import copy as raster_copy
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds


def tile_bounds(z, x, y):
    if not (0 <= z <= 22 and 0 <= x < 2**z and 0 <= y < 2**z):
        raise ValueError("Invalid XYZ tile")
    extent = 20037508.342789244
    step = extent * 2 / 2**z
    return (
        -extent + x * step,
        extent - (y + 1) * step,
        -extent + (x + 1) * step,
        extent - y * step,
    )


def rgba_png(data, alpha, ranges=None):
    rgb = np.zeros(data.shape, dtype="uint8")
    for index, band in enumerate(data):
        if data.dtype == np.uint8:
            rgb[index] = band
        else:
            if ranges is None:
                raise ValueError("Global display ranges required for non-byte imagery")
            low, high = ranges[index]
            rgb[index] = np.clip(
                np.nan_to_num((band - low) / max(float(high - low), 1e-9)) * 255, 0, 255
            ).astype("uint8")
    with MemoryFile() as memory:
        with memory.open(
            driver="PNG", width=data.shape[2], height=data.shape[1], count=4, dtype="uint8"
        ) as out:
            out.write(np.concatenate([rgb, alpha[None].astype("uint8")]))
        return memory.read()


def convert(source, cog, thumbnail, max_pixels):
    with rasterio.open(source) as ds:
        if not ds.crs or ds.width * ds.height > max_pixels:
            raise ValueError("invalid_crs_or_pixel_limit")
        bbox = list(transform_bounds(ds.crs, "EPSG:4326", *ds.bounds, densify_pts=21))
        if not all(math.isfinite(v) for v in bbox) or not (
            -180 <= bbox[0] < bbox[2] <= 180 and -85.0511 <= bbox[1] < bbox[3] <= 85.0511
        ):
            raise ValueError("unsupported_geographic_extent")
        nodata = float(ds.nodata) if ds.nodata is not None and math.isfinite(ds.nodata) else None
        meta = {
            "width": ds.width,
            "height": ds.height,
            "bands": ds.count,
            "dtype": ds.dtypes[0],
            "nodata": nodata,
            "crs": ds.crs.to_string(),
            "resolution": list(ds.res),
            "bbox": bbox,
        }
        indexes = [1, 2, 3] if ds.count >= 3 else [1, 1, 1]
        scale = min(1, 256 / max(ds.width, ds.height))
        h, w = max(1, round(ds.height * scale)), max(1, round(ds.width * scale))
        data = ds.read(indexes, out_shape=(3, h, w), resampling=Resampling.bilinear)
        alpha = ds.dataset_mask(out_shape=(h, w))
        with open(thumbnail, "wb") as target:
            ranges = []
            for band in data:
                valid = band[(alpha > 0) & np.isfinite(band)]
                low, high = (
                    (0, 255)
                    if data.dtype == np.uint8
                    else (np.percentile(valid, [2, 98]) if valid.size else (0, 1))
                )
                if low == high:
                    low, high = low - 0.5, high + 0.5
                ranges.append([float(low), float(high)])
            meta["display_ranges"] = ranges
            target.write(rgba_png(data, alpha, ranges))
    raster_copy(
        source,
        cog,
        driver="COG",
        BLOCKSIZE=512,
        COMPRESS="DEFLATE",
        NUM_THREADS="2",
        BIGTIFF="IF_SAFER",
    )
    with rasterio.open(cog) as ds:
        if ds.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") != "COG":
            raise RuntimeError("cog_validation_failed")
    return meta


def render_tile(url, z, x, y, ranges=None):
    bounds = tile_bounds(z, x, y)
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        GDAL_HTTP_TIMEOUT="15",
        GDAL_HTTP_MAX_RETRY="1",
        GDAL_CACHEMAX=64 * 1024 * 1024,
    ):
        with rasterio.open(url) as ds:
            with WarpedVRT(
                ds,
                crs="EPSG:3857",
                transform=from_bounds(*bounds, 256, 256),
                width=256,
                height=256,
                add_alpha=ColorInterp.alpha not in ds.colorinterp,
                resampling=Resampling.bilinear,
            ) as vrt:
                indexes = [1, 2, 3] if ds.count >= 3 else [1, 1, 1]
                return rgba_png(vrt.read(indexes), vrt.dataset_mask(), ranges)

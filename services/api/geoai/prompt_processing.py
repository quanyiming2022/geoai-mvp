"""Bounded native-CRS image/mask crop, with shared pixel grid."""
import math
import numpy as np
import rasterio
from rasterio.features import geometry_window, geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import transform as window_transform
from rasterio.io import MemoryFile


def support_crop(source, geometry):
    with rasterio.Env(GDAL_HTTP_TIMEOUT="15", GDAL_HTTP_MAX_RETRY="1", GDAL_CACHEMAX=64*1024*1024, GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        with rasterio.open(source) as ds:
            shape = transform_geom("EPSG:4326", ds.crs, geometry)
            inverse = ~ds.transform
            for ring in shape['coordinates']:
                for coordinate in ring:
                    x, y = inverse * tuple(coordinate[:2])
                    if not (-1e-6 <= x <= ds.width + 1e-6 and -1e-6 <= y <= ds.height + 1e-6):
                        raise ValueError("Sample extends outside the raster pixel footprint")
            window = geometry_window(ds, [shape], pad_x=8, pad_y=8)
            if window.width * window.height > 4_000_000 or ds.count > 16:
                raise ValueError("Sample too large; draw a smaller target")
            scale = max(window.width / 512, window.height / 512, 1)
            width, height = math.ceil(window.width / scale), math.ceil(window.height / scale)
            transform = window_transform(window, ds.transform) * rasterio.Affine.scale(window.width / width, window.height / height)
            data = ds.read(window=window, out_shape=(ds.count,height,width), resampling=rasterio.enums.Resampling.nearest)
            valid = ds.dataset_mask(window=window, out_shape=(height,width)) > 0
            mask = (geometry_mask([shape], out_shape=(height,width), transform=transform, invert=True) & valid).astype('uint8')
            if not mask.any():
                raise ValueError("Sample contains no valid target pixels")
            profile = dict(driver='GTiff', width=width,height=height,crs=ds.crs,transform=transform,compress='deflate')
            blobs = []
            for array in (data, mask[np.newaxis]):
                with MemoryFile() as memory:
                    with memory.open(**profile, count=array.shape[0], dtype=array.dtype) as target:
                        target.write(array)
                    blobs.append(memory.read())
            return blobs[0], blobs[1], ds.crs.to_string()

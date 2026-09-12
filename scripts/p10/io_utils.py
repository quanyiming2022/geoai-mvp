"""Lossless offline experiment artifact writers; PNG carries no georeference."""
import numpy as np
import rasterio

def png(path, data):
    data = np.asarray(data, dtype="uint8")
    data = data[None] if data.ndim == 2 else data
    with rasterio.open(path, "w", driver="PNG", width=data.shape[2], height=data.shape[1], count=data.shape[0], dtype="uint8") as dst:
        dst.write(data)

def tif(path, data, crs, transform):
    data = np.asarray(data)
    data = data[None] if data.ndim == 2 else data
    with rasterio.open(path, "w", driver="GTiff", width=data.shape[2], height=data.shape[1], count=data.shape[0], dtype=data.dtype, crs=crs, transform=transform, compress="deflate") as dst:
        dst.write(data)

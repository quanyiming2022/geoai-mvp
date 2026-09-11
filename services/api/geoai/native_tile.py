"""P9-only exact source-resolution windows. P8 preview resampling is unchanged."""
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import geometry_mask,geometry_window
from rasterio.warp import transform_geom


def _window(ds,col,row):
    if type(col) is not int or type(row) is not int or min(col,row)<0 or col+512>ds.width or row+512>ds.height:
        raise ValueError('Select a full 512x512 window inside the source raster')
    return Window(col,row,512,512)


def _rgb(ds,window,ranges):
    if ds.count<3:
        raise ValueError('Real model requires a raster with RGB bands')
    values=ds.read((1,2,3),window=window)  # No out_shape, overview, warp or resampling.
    if values.dtype==np.uint8:
        return values
    if not ranges or len(ranges)<3:
        raise ValueError('Non-byte RGB requires explicit recorded display ranges')
    rgb=[]
    for band,(low,high) in zip(values,ranges[:3]):
        if not np.isfinite([low,high]).all() or high<=low:
            raise ValueError('Invalid RGB display range')
        rgb.append(np.clip(np.nan_to_num((band.astype('float32')-low)/(high-low))*255,0,255).astype('uint8'))
    return np.stack(rgb)


def read_native_tile(source,col,row,ranges=None):
    with rasterio.Env(GDAL_HTTP_TIMEOUT='15',GDAL_HTTP_MAX_RETRY='1',GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
        with rasterio.open(source) as ds:
            window=_window(ds,col,row)
            return _rgb(ds,window,ranges),ds.dataset_mask(window=window)>0,ds.window_transform(window),ds.crs.to_string()


def read_support_tile(source,geometry,ranges=None):
    with rasterio.Env(GDAL_HTTP_TIMEOUT='15',GDAL_HTTP_MAX_RETRY='1',GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
        with rasterio.open(source) as ds:
            shape=transform_geom('EPSG:4326',ds.crs,geometry)
            extent=geometry_window(ds,[shape],boundless=True)
            if extent.width>512 or extent.height>512 or extent.col_off<0 or extent.row_off<0 or extent.col_off+extent.width>ds.width or extent.row_off+extent.height>ds.height:
                raise ValueError('Support target must fit in one source-resolution 512x512 tile')
            col=max(0,min(ds.width-512,int(extent.col_off+extent.width/2)-256))
            row=max(0,min(ds.height-512,int(extent.row_off+extent.height/2)-256))
            window=_window(ds,col,row)
            transform=ds.window_transform(window)
            mask=geometry_mask([shape],out_shape=(512,512),transform=transform,invert=True)&(ds.dataset_mask(window=window)>0)
            if not mask.any():
                raise ValueError('Support target has no valid pixels')
            return _rgb(ds,window,ranges),mask.astype('uint8')[None],{'col_off':col,'row_off':row}

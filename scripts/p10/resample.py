"""Georeferenced diagnostic grids; rejects insufficient source coverage instead of padding."""
import numpy as np
from affine import Affine
from rasterio.warp import reproject,Resampling

def grid_for(ds,center_col,center_row,gsd,size=512):
    t=ds.transform
    if not ds.crs or not ds.crs.is_projected or ds.crs.linear_units!='metre' or t.b or t.d or t.a<=0 or t.e>=0:raise ValueError('Requires north-up projected metre raster')
    sx=size*gsd/t.a;sy=size*gsd/abs(t.e)
    if sx>ds.width or sy>ds.height:raise ValueError('INSUFFICIENT_SOURCE_FOOTPRINT')
    col=max(0,min(center_col-sx/2,ds.width-sx));row=max(0,min(center_row-sy/2,ds.height-sy))
    x,y=t*(col,row)
    return Affine(gsd,0,x,0,-gsd,y)

def rgb_grid(ds,transform,size=512):
    out=np.zeros((3,size,size),dtype=ds.dtypes[0]);valid=np.zeros((size,size),dtype='uint8')
    for i in range(3):
        reproject(ds.read(i+1),out[i],src_transform=ds.transform,src_crs=ds.crs,dst_transform=transform,dst_crs=ds.crs,resampling=Resampling.bilinear)
    reproject(ds.dataset_mask(),valid,src_transform=ds.transform,src_crs=ds.crs,dst_transform=transform,dst_crs=ds.crs,resampling=Resampling.nearest)
    if not np.all(valid):raise ValueError('INVALID_SOURCE_PIXELS')
    return out

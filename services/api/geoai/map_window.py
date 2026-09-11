"""Map point -> native model context window, distinct from the effective AOI."""
import math
from rasterio.warp import transform,transform_geom
from rasterio.windows import Window
from rasterio.features import geometry_window


def transformed_footprint(t,crs):
    ring=[list(t*p) for p in [(0,0),(512,0),(512,512),(0,512),(0,0)]]
    return transform_geom(crs,'EPSG:4326',{'type':'Polygon','coordinates':[ring]})


def window_footprint(ds,col,row):
    if min(col,row)<0 or col+512>ds.width or row+512>ds.height:
        raise ValueError('模型输入窗口必须完整位于影像内')
    t=ds.window_transform(Window(col,row,512,512))
    return transformed_footprint(t,ds.crs)


def select_window(ds,longitude,latitude,aoi_geometry=None):
    if ds.width<512 or ds.height<512 or ds.count<3:raise ValueError('请选择至少 512×512 的 RGB 影像')
    x,y=transform('EPSG:4326',ds.crs,[longitude],[latitude])
    row,col=ds.index(x[0],y[0])
    if not (0<=col<ds.width and 0<=row<ds.height):raise ValueError('请在所选影像范围内点击')
    col=max(0,min(ds.width-512,col-256));row=max(0,min(ds.height-512,row-256))
    if aoi_geometry:
        extent=geometry_window(ds,[transform_geom('EPSG:4326',ds.crs,aoi_geometry)],boundless=True)
        if extent.width<=512 and extent.height<=512:
            # Keep all of a small AOI in the model context where source coverage permits.
            col=max(0,min(ds.width-512,min(max(col,math.ceil(extent.col_off+extent.width)-512),math.floor(extent.col_off))))
            row=max(0,min(ds.height-512,min(max(row,math.ceil(extent.row_off+extent.height)-512),math.floor(extent.row_off))))
    return {'query_col':col,'query_row':row,'geometry':window_footprint(ds,col,row),'execution_scope':'single_tile','width':512,'height':512}


def job_window_bounds(repo,project_id,data):
    """Read authoritative COG georeferencing before snapshot insertion; no pixel read."""
    import rasterio
    from fastapi import HTTPException
    from .config import Settings
    from .rasters import provider
    rows=repo.execute("SELECT cog_object_key FROM raster_assets WHERE id=%s AND project_id=%s AND status='ready'",(data.raster_asset_id,project_id))
    expected=f'{project_id}/rasters/{data.raster_asset_id}/cog.tif'
    if not rows or rows[0]['cog_object_key']!=expected:raise HTTPException(422,'所选影像尚不可用')
    cfg=Settings();storage=provider(cfg,internal=True)
    try:
        with rasterio.Env(GDAL_HTTP_TIMEOUT='15',GDAL_HTTP_MAX_RETRY='1'):
            with rasterio.open(storage.create_signed_url(cfg.storage_bucket,expected,60)) as ds:
                return window_footprint(ds,data.query_col,data.query_row)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    except rasterio.errors.RasterioError:raise HTTPException(503,'暂时无法读取模型窗口，请稍后重试') from None
    finally:storage.close()

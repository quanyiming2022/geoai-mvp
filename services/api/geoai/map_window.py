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
    rows=repo.execute("SELECT cog_object_key,storage_project_id FROM project_rasters WHERE id=%s AND project_id=%s AND status='ready'",(data.raster_asset_id,project_id))
    expected=f"{rows[0]['storage_project_id'] if rows else project_id}/rasters/{data.raster_asset_id}/cog.tif"
    if not rows or rows[0]['cog_object_key']!=expected:raise HTTPException(422,'所选影像尚不可用')
    cfg=Settings();storage=provider(cfg,internal=True)
    try:
        with rasterio.Env(GDAL_HTTP_TIMEOUT='15',GDAL_HTTP_MAX_RETRY='1'):
            with rasterio.open(storage.create_signed_url(cfg.storage_bucket,expected,60)) as ds:
                return window_footprint(ds,data.query_col,data.query_row)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    except rasterio.errors.RasterioError:raise HTTPException(503,'暂时无法读取模型窗口，请稍后重试') from None
    finally:storage.close()


def plan_full_aoi(ds,geometry):
    """Resolve geographic coverage using the inverse source affine, including rotation.

    Snap only round-trip numerical noise (<1e-7 source pixel). Never use a
    geographic bbox or a resized preview to infer native pixel capacity.
    """
    local=transform_geom('EPSG:4326',ds.crs,geometry)
    def points(value):
        if isinstance(value[0],(float,int)):yield value
        else:
            for part in value:yield from points(part)
    pixels=[(~ds.transform)*(p[0],p[1]) for p in points(local['coordinates'])]
    def snap(v):return float(round(v)) if abs(v-round(v))<1e-7 else v
    left,top=map(snap,(min(p[0] for p in pixels),min(p[1] for p in pixels)))
    right,bottom=map(snap,(max(p[0] for p in pixels),max(p[1] for p in pixels)))
    width,height=right-left,bottom-top
    plan={'requested_scope':'full_aoi','execution_mode':'single_tile_full_aoi','available':False,'aoi_bbox_width_px':width,'aoi_bbox_height_px':height,'model_input_width':512,'model_input_height':512}
    if width>512 or height>512:return {**plan,'execution_mode':'multi_tile_full_aoi','reason':'multi_tile_required'}
    if left<0 or top<0 or right>ds.width or bottom>ds.height:return {**plan,'reason':'outside_raster'}
    if ds.width<512 or ds.height<512 or ds.count<3:return {**plan,'reason':'source_too_small'}
    col_min=max(0,math.ceil(right-512));col_max=min(ds.width-512,math.floor(left))
    row_min=max(0,math.ceil(bottom-512));row_max=min(ds.height-512,math.floor(top))
    if col_min>col_max or row_min>row_max:return {**plan,'reason':'pixel_alignment'}
    col=max(col_min,min(col_max,math.floor((left+right-512)/2)))
    row=max(row_min,min(row_max,math.floor((top+bottom-512)/2)))
    return {**plan,'available':True,'reason':None,'query_col':col,'query_row':row,'width':512,'height':512,'geometry':window_footprint(ds,col,row)}


def resolve_full_aoi(project_id,current,raster_id,aoi_id):
    """Authorized COG header + AOI read. No model calls or writes."""
    import rasterio,httpx
    from fastapi import HTTPException
    from .spatial import UserSQLRepository
    from .config import Settings
    from .rasters import provider
    repo=UserSQLRepository(current.user['id'])
    rows=repo.execute("SELECT a.revision,extensions.ST_AsGeoJSON(a.geometry,17)::json AS geometry,r.cog_object_key,r.storage_project_id FROM aois a JOIN project_rasters r ON r.project_id=a.project_id WHERE a.id=%s AND r.id=%s AND a.project_id=%s AND a.deleted_at IS NULL AND r.status='ready'",(aoi_id,raster_id,project_id))
    if not rows:raise HTTPException(422,'请选择当前项目中可用的影像与 AOI。')
    row=rows[0];key=f"{row['storage_project_id']}/rasters/{raster_id}/cog.tif"
    if row['cog_object_key']!=key:raise HTTPException(422,'影像尚不可用。')
    cfg=Settings();storage=provider(cfg,internal=True)
    try:
        with rasterio.Env(GDAL_HTTP_TIMEOUT='15',GDAL_HTTP_MAX_RETRY='1'):
            with rasterio.open(storage.create_signed_url(cfg.storage_bucket,key,60)) as ds:
                return {**plan_full_aoi(ds,row['geometry']),'raster_id':str(raster_id),'aoi_id':str(aoi_id),'aoi_revision':row['revision']}
    except (ValueError,httpx.HTTPError,rasterio.errors.RasterioError):raise HTTPException(503,'暂时无法检查范围覆盖能力，请稍后重试。') from None
    finally:storage.close()

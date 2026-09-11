"""Read-only map point to existing native window parameters; no inference/resampling."""
from rasterio.warp import transform,transform_geom
from rasterio.windows import Window


def select_window(ds,longitude,latitude):
    if ds.width<512 or ds.height<512 or ds.count<3:raise ValueError('请选择至少 512×512 的 RGB 影像')
    x,y=transform('EPSG:4326',ds.crs,[longitude],[latitude])
    row,col=ds.index(x[0],y[0])
    if not (0<=col<ds.width and 0<=row<ds.height):raise ValueError('请在所选影像范围内点击')
    col=max(0,min(ds.width-512,col-256));row=max(0,min(ds.height-512,row-256))
    t=ds.window_transform(Window(col,row,512,512))
    ring=[list(t*p) for p in [(0,0),(512,0),(512,512),(0,512),(0,0)]]
    return {'query_col':col,'query_row':row,'geometry':transform_geom(ds.crs,'EPSG:4326',{'type':'Polygon','coordinates':[ring]}),'execution_scope':'single_tile','width':512,'height':512}

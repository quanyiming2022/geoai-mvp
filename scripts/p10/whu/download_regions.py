import sys,json,hashlib,time,threading,http.server,shutil,zipfile,os
from pathlib import Path
from urllib.parse import quote
import httpx,numpy as np,rasterio,shapefile
from rasterio.windows import Window
from rasterio.enums import Resampling
from rasterio.features import rasterize
from affine import Affine
from whu_range import Remote
D=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'))
# Retrieve only small full-area label members to establish satellite chip georeferencing.
u='https://gpcv.whu.edu.cn/data/'+quote('Satellite dataset Ⅱ (East Asia).zip');r=Remote(u);z=zipfile.ZipFile(r)
for i in z.infolist():
 if '/3. The whole area image dataset/label/' in i.filename and i.filename.endswith(('.tif','.tfw')):
  p=D/'satellite-ii/whole-labels'/Path(i.filename).name;p.parent.mkdir(parents=True,exist_ok=True)
  if not p.exists():
   with z.open(i) as src,p.open('wb') as f:shutil.copyfileobj(src,f,1024**2)
  print('whole label',p.name,p.stat().st_size,flush=True)
# Bounded HTTP range proxy provides an actual transfer ceiling for GDAL access.
url='https://gpcv.whu.edu.cn/data/'+quote('1.the whole aerial image.tif')
state={'bytes':0,'requests':0,'max_bytes':384*1024**2};lock=threading.Lock();client=httpx.Client(timeout=60,follow_redirects=True)
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_HEAD(self):
  self.send_response(200);self.send_header('Content-Length','26301690701');self.send_header('Accept-Ranges','bytes');self.end_headers()
 def do_GET(self):
  h=self.headers.get('Range','')
  try:
   assert h.startswith('bytes=') and ',' not in h;lo,hi=map(int,h[6:].split('-'));n=hi-lo+1
   with lock:
    assert state['bytes']+n<=state['max_bytes'],'transfer budget exceeded';state['bytes']+=n;state['requests']+=1
    if state['requests']%50==0:print('HTTP range progress',state,flush=True)
   rr=client.get(url,headers={'Range':h});assert rr.status_code==206 and len(rr.content)==n
   self.send_response(206);self.send_header('Content-Length',str(n));self.send_header('Content-Range',rr.headers['content-range']);self.send_header('Content-Type','image/tiff');self.end_headers();self.wfile.write(rr.content)
  except Exception as e:print('RANGE ERROR',str(e),flush=True);self.send_error(502)
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
reader=shapefile.Reader(str(D/'aerial-vectors/allbuilding.shp'));records=[]
try:
 with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR',GDAL_HTTP_TIMEOUT='90',GDAL_HTTP_MAX_RETRY='0',GDAL_HTTP_MULTIRANGE='SERIAL',GDAL_CACHEMAX=256*1024**2):
  with rasterio.open(f'/vsicurl/http://127.0.0.1:{server.server_port}/whu.tif',overview_level=1) as ds:
   for name,cx,cy in [('christchurch-urban',1570800,5180800),('christchurch-outskirts',1565000,5188000)]:
    folder=D/'aerial'/name;folder.mkdir(parents=True,exist_ok=True);p=folder/'image_0p3m.tif'
    assert not p.exists(),'Do not overwrite frozen crop'
    native=Affine(0.07499999999999182,0,1551435.325,0,-0.0749999999999956,5196120.0)
    col,row=(~native)*(cx,cy);col=int(col//4)*4-15360;row=int(row//4)*4-15360;native_win=Window(col,row,30720,30720)
    bounds=rasterio.windows.bounds(native_win,native);win=rasterio.windows.from_bounds(*bounds,ds.transform);transform=rasterio.windows.transform(native_win,native)*Affine.scale(4);shape=(7680,7680)
    print('Explicit overview',ds.shape,ds.res,flush=True)
    print('reading',name,'source window',list(win.flatten()),'derived 0.3m',flush=True)
    rgb=ds.read([1,2,3],window=win,out_shape=(3,*shape),resampling=Resampling.bilinear)
    # Preserve explicit input no-data mask. Nodata=255 per original TIFF.
    valid=ds.dataset_mask(window=win,out_shape=shape,resampling=Resampling.nearest)>0
    profile=dict(driver='GTiff',width=7680,height=7680,count=3,dtype='uint8',crs=ds.crs,transform=transform,tiled=True,blockxsize=256,blockysize=256,compress='deflate',predictor=2,BIGTIFF='IF_SAFER')
    with rasterio.open(p,'w',**profile) as dst:dst.write(rgb);dst.write_mask(valid.astype('uint8')*255);dst.update_tags(source_url=url,source_native_gsd_m='0.075',derived_gsd_m='0.3',resampling='GDAL bilinear, explicit official internal overview factor 4')
    features=[]
    with shapefile.Writer(str(folder/'buildings'),shapeType=reader.shapeType) as writer:
     writer.fields=reader.fields[1:]
     for sr in reader.iterShapeRecords(bbox=bounds):
      writer.shape(sr.shape);writer.record(*sr.record);features.append(sr.shape.__geo_interface__)
    shutil.copyfile(D/'aerial-vectors/allbuilding.prj',folder/'buildings.prj')
    gt=rasterize([(g,1) for g in features],out_shape=shape,transform=transform,dtype='uint8')
    with rasterio.open(folder/'building_gt_0p3m.tif','w',**{**profile,'count':1,'predictor':1}) as dst:dst.write(gt,1);dst.write_mask(valid.astype('uint8')*255)
    preview=rgb[:,::10,::10].copy();mask=gt[::10,::10]>0;preview[:,mask]=(.65*preview[:,mask]+.35*np.array([255,40,40])[:,None]).astype('uint8')
    with rasterio.open(folder/'gt-overlay.png','w',driver='PNG',width=768,height=768,count=3,dtype='uint8') as dst:dst.write(preview)
    rec={'name':name,'source_url':url,'source_size_bytes':26301690701,'source_native_gsd_m':.075,'source_window':list(native_win.flatten()),'overview_window':list(win.flatten()),'source_crs':str(ds.crs),'output_gsd_m':.3,'output_transform':list(transform)[:6],'output_shape':list(shape),'bounds':list(bounds),'width_m':2304,'height_m':2304,'building_vector_features':len(features),'valid_fraction':float(valid.mean()),'resampling':'bilinear; explicit official 4x overview; not a native 0.3m sensor acquisition','range_bytes_so_far':state['bytes']}
    (folder/'metadata.json').write_text(json.dumps(rec,indent=2));records.append(rec);print('DONE',rec,flush=True)
finally:
 server.shutdown();(D/'aerial-download.json').write_text(json.dumps({'regions':records,'transfer':state},indent=2))

from pathlib import Path
import json,math,hashlib,os
import rasterio,numpy as np,shapefile
from rasterio.features import rasterize
from rasterio.warp import transform
from affine import Affine
D=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'))/'satellite-ii'
rows=json.loads((D/'chip-placement.json').read_text());assert len(rows)==4 and len(set(x['image'] for x in rows))==4
crs=rasterio.crs.CRS.from_wkt((D/'vectors/EA.prj').read_text());r=shapefile.Reader(str(D/'vectors/EA.shp'));results=[]
for row in rows:
 aff=Affine(*row['transform']);features=[s.__geo_interface__ for s in r.iterShapes(bbox=tuple(row['bounds']))]
 vector=rasterize([(g,1) for g in features],out_shape=(512,512),transform=aff,dtype='uint8')
 with rasterio.open(D/'image'/row['image']) as ds:rgb=ds.read()
 with rasterio.open(D/'label'/row['image']) as ds:gt=(ds.read(1)>0).astype('uint8')
 union=((gt>0)|(vector>0)).sum();iou=float(((gt>0)&(vector>0)).sum()/union) if union else None
 assert iou is not None and iou>.9,('Vector/world-file consistency failed',row['image'],iou)
 folder=D/'georeferenced'/Path(row['image']).stem;folder.mkdir(parents=True,exist_ok=True)
 for name,a in [('image.tif',rgb),('building_gt.tif',gt[None])]:
  with rasterio.open(folder/name,'w',driver='GTiff',height=512,width=512,count=a.shape[0],dtype=a.dtype,crs=crs,transform=aff,compress='deflate') as out:out.write(a)
 overlay=rgb.copy();mask=gt>0;overlay[:,mask]=(.6*rgb[:,mask]+.4*np.array([255,40,40])[:,None]).astype('uint8')
 with rasterio.open(folder/'gt-overlay.png','w',driver='PNG',height=512,width=512,count=3,dtype='uint8') as out:out.write(overlay)
 p=aff*(256,256);px=aff*(257,256);py=aff*(256,257);xx,yy=transform(crs,'EPSG:32651',[p[0],px[0],py[0]],[p[1],px[1],py[1]])
 gsd=[math.hypot(xx[i]-xx[0],yy[i]-yy[0]) for i in [1,2]]
 results.append({**row,'derived_crs':str(crs),'crs_provenance':'official EA.prj; accepted only after vector-to-matched-raster IoU>0.9','vector_raster_iou':iou,'gt_pixels':int(gt.sum()),'approx_ground_gsd_m_in_utm51':gsd,'official_web_gsd_m':2.7,'gsd_conflict':'official web says 2.7m; matched whole-label affine and official vector geometry imply approximately 0.26m. Do not report this subset as 2.7m.'})
print(json.dumps(results,indent=2));(D/'validation.json').write_text(json.dumps(results,indent=2))

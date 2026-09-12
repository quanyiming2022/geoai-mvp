"""Validate derived WHU data, create legal georeferenced scale inputs, and hash files."""
from pathlib import Path
import json,hashlib,sys,os
import numpy as np,rasterio,shapefile
from affine import Affine
from rasterio.features import rasterize
from rasterio.warp import reproject,Resampling
D=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'))
records=[]
for name in ['christchurch-urban','christchurch-outskirts']:
 folder=D/'aerial'/name;gtpath=folder/'building_gt_0p3m.tif'
 with rasterio.open(folder/'image_0p3m.tif') as ds,rasterio.open(gtpath) as truth:
  assert ds.crs==truth.crs and ds.transform==truth.transform and ds.shape==truth.shape
  assert ds.width==ds.height==7680 and ds.crs.to_epsg()==2193
  assert np.allclose(ds.res,[.3,.3]);features=[s.__geo_interface__ for s in shapefile.Reader(str(folder/'buildings.shp')).iterShapes()]
  cx,cy=ds.transform*(3840,3840)
  for gsd in [1.,1.5,2.,3.,4.]:
   transform=Affine(gsd,0,cx-gsd*256,0,-gsd,cy+gsd*256)
   assert ds.bounds.left<=transform.c and ds.bounds.right>=transform.c+512*gsd and ds.bounds.bottom<=transform.f-512*gsd and ds.bounds.top>=transform.f
   out=folder/'scale-inputs'/f'{gsd:g}m';out.mkdir(parents=True,exist_ok=True)
   # Read the same continuous georeferenced source; no PNG resizing and no padding.
   rgb=np.zeros((3,512,512),dtype='uint8')
   for b in range(1,4):reproject(rasterio.band(ds,b),rgb[b-1],src_transform=ds.transform,src_crs=ds.crs,dst_transform=transform,dst_crs=ds.crs,resampling=Resampling.bilinear)
   valid=np.zeros((512,512),dtype='uint8');reproject(ds.dataset_mask(),valid,src_transform=ds.transform,src_crs=ds.crs,dst_transform=transform,dst_crs=ds.crs,resampling=Resampling.nearest)
   gt=rasterize([(g,1) for g in features],out_shape=(512,512),transform=transform,dtype='uint8')
   for filename,a in [('image.tif',rgb),('building_gt.tif',gt[None]),('valid_mask.tif',valid[None])]:
    with rasterio.open(out/filename,'w',driver='GTiff',height=512,width=512,count=a.shape[0],dtype=a.dtype,crs=ds.crs,transform=transform,compress='deflate') as dst:dst.write(a)
   records.append({'region':name,'gsd_m':gsd,'shape':[512,512],'crs':str(ds.crs),'transform':list(transform)[:6],'valid_pixels':int((valid>0).sum()),'full_coverage':bool((valid>0).all()),'gt_pixels':int(gt.sum()),'gt_policy':'rasterize original official building vectors on target grid; pixel center rule','physical_width_m':512*gsd,'same_source_center':True,'fov_note':'different GSD at fixed model size changes physical FOV; use a common geographic evaluation core to isolate scale in later experiments'})
assert len(records)==10
(D/'scale-input-validation.json').write_text(json.dumps(records,indent=2))
files=[]
for p in sorted(D.rglob('*')):
 if p.is_file() and not p.name.startswith('._') and p.name!='sha256-manifest.json':
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1024**2),b''):h.update(b)
  files.append({'path':str(p.relative_to(D)),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
(D/'sha256-manifest.json').write_text(json.dumps(files,indent=2))
print(json.dumps(records,indent=2));print('HASHED',len(files),'files',sum(x['bytes'] for x in files),'bytes')

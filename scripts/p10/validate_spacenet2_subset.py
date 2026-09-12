"""Validate downloaded official image/label pairs; derive traceable binary GT and display previews."""
import hashlib,json
from pathlib import Path
import numpy as np,rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from migrate import connection
from rasterio.warp import transform
from download_spacenet2_subset import DEST

def run():
 manifest=json.loads((DEST/'manifest.json').read_text());rows=[];conn=connection();conn.execute('SET TRANSACTION READ ONLY')
 for pair in manifest['pairs']:
  for obj in pair['objects']:
   p=DEST/obj['file'];assert p.stat().st_size==obj['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==obj['sha256']
  tif=next(DEST/o['file'] for o in pair['objects'] if o['file'].endswith('.tif'));label=next(DEST/o['file'] for o in pair['objects'] if o['file'].endswith('.geojson'))
  data=json.loads(label.read_text());label_crs=data.get('crs',{}).get('properties',{}).get('name','EPSG:4326');features=data['features'];name=tif.stem.split('_PS-RGB_')[-1];out=DEST/pair['city']/'derived'/name;out.mkdir(parents=True,exist_ok=True)
  with rasterio.open(tif) as ds:
   assert ds.count==3 and ds.width>=512 and ds.height>=512 and ds.crs
   rgb=ds.read();geometries=[];invalid=0
   valid=(ds.dataset_mask()>0)&np.any(rgb>0,axis=0)
   integral=np.pad(valid.astype('int32'),((1,0),(1,0))).cumsum(0).cumsum(1)
   windows=integral[512:,512:]-integral[:-512,512:]-integral[512:,:-512]+integral[:-512,:-512]
   full_window=bool(windows.max()==512**2)
   if pair.get('selected_for_p10',True):assert full_window,'No full valid 512 window'
   with rasterio.open(out/'valid_mask.png','w',driver='PNG',width=ds.width,height=ds.height,count=1,dtype='uint8') as dst:dst.write(valid.astype('uint8')*255,1)
   for f in features:
    if not f.get('geometry'):continue
    geom=transform_geom(label_crs,ds.crs,f['geometry'])
    valid,overlap=conn.execute('SELECT ST_IsValid(g), ST_Intersects(ST_SetSRID(g,0),ST_MakeEnvelope(%s,%s,%s,%s,0)) FROM (SELECT ST_GeomFromGeoJSON(%s) g) q',(*ds.bounds,json.dumps(geom))).fetchone()
    if not valid:invalid+=1;continue
    assert overlap,'Annotation outside matching image'
    geometries.append(geom)
   assert invalid==0,'Invalid source geometries need review, not silent repair'
   gt=rasterize([(g,1) for g in geometries],out_shape=(ds.height,ds.width),transform=ds.transform,dtype='uint8') if geometries else np.zeros((ds.height,ds.width),dtype='uint8')
   with rasterio.open(out/'building_gt.tif','w',driver='GTiff',width=ds.width,height=ds.height,count=1,dtype='uint8',crs=ds.crs,transform=ds.transform,compress='deflate') as dst:dst.write(gt,1);dst.update_tags(annotation_source=pair['objects'][1]['url'],method='official building polygons rasterized, pixel center rule, no geometry repairs')
   with rasterio.open(out/'building_gt.png','w',driver='PNG',width=ds.width,height=ds.height,count=1,dtype='uint8') as dst:dst.write(gt*255,1)
   # Visualization only; never a silently substituted model input.
   display=np.zeros_like(rgb,dtype='uint8')
   for b in range(3):
    values=rgb[b][ds.dataset_mask()>0];low,high=np.percentile(values,[2,98]);display[b]=np.clip((rgb[b].astype(float)-low)*255/max(high-low,1),0,255).astype('uint8')
   with rasterio.open(out/'preview.png','w',driver='PNG',width=ds.width,height=ds.height,count=3,dtype='uint8') as dst:dst.write(display)
   overlay=display.copy();overlay[:,gt>0]=(.65*display[:,gt>0]+.35*np.array([255,35,35])[:,None]).astype('uint8')
   with rasterio.open(out/'label-overlay.png','w',driver='PNG',width=ds.width,height=ds.height,count=3,dtype='uint8') as dst:dst.write(overlay)
   p=ds.transform*(ds.width/2,ds.height/2);px=ds.transform*(ds.width/2+1,ds.height/2);py=ds.transform*(ds.width/2,ds.height/2+1)
   xs,ys=transform(ds.crs,'EPSG:4326',[p[0],px[0],py[0]],[p[1],px[1],py[1]])
   gsd=[conn.execute('SELECT ST_Distance(ST_SetSRID(ST_Point(%s,%s),4326)::geography,ST_SetSRID(ST_Point(%s,%s),4326)::geography)',(xs[0],ys[0],xs[i],ys[i])).fetchone()[0] for i in [1,2]]
   rows.append({'city':pair['city'],'selected_for_p10':pair.get('selected_for_p10',True),'full_512_valid_window':full_window,'image_id':name,'width':ds.width,'height':ds.height,'bands':ds.count,'dtype':ds.dtypes[0],'crs':str(ds.crs),'transform':list(ds.transform)[:6],'approx_center_gsd_m':gsd,'building_features':len(geometries),'building_pixels':int(gt.sum()),'valid_pixels':int((ds.dataset_mask()>0).sum()),'gt_source':'official SpaceNet2 training annotations','preview_only':'2–98 percentile display stretch; raw uint16 imagery unchanged'})
 conn.close()
 (DEST/'validation.json').write_text(json.dumps(rows,indent=2))
 total=sum(o['bytes'] for p in manifest['pairs'] for o in p['objects'])
 (DEST/'README.md').write_text(f'''# SpaceNet 2 — P10 small subset

8 active matched pairs: Shanghai 4, Las Vegas 4. One rejected Vegas black-border pair is retained separately in the manifest (9 downloaded pairs total). Raw download {total:,} bytes ({total/1024**2:.2f} MiB). No city tarballs, PAN or MS downloaded.

Official source: https://spacenet.ai/spacenet-buildings-dataset-v2/
License reported by source: Creative Commons Attribution-ShareAlike 4.0 International (https://creativecommons.org/licenses/by-sa/4.0/).
Citation: Van Etten, A., Lindenbaum, D., & Bacastow, T.M. (2018). SpaceNet: A Remote Sensing Dataset and Challenge Series. arXiv:1807.01232.

`manifest.json`: original URLs, sizes, ETags and SHA256. `validation.json`: geography, GSD and label counts.
`PS-RGB/` and `geojson_buildings/` retain original bytes. `derived/`: binary official-label GT, display-only preview and label overlay. Pixel-center rasterization; no geometry repair. Raw imagery is uint16; previews are not approved model inputs.

Selection is a limited convenience/label-presence-stratified pilot (first 1000 keys), not a representative city evaluation or random test split. Official training labels are used; report potential model pretraining overlap separately. Building footprint labels may differ from visible roof boundaries; inspect alignment before scoring.

These small ~200m training chips provide building GT but do not supply the physical footprint needed for a 512-pixel query at 1–4m. They supplement, not replace, the frozen SPOT6 scale baseline. No change to model preprocessing or inference performed by this download.
''')
 print(json.dumps(rows,indent=2));print('PASS: all original pairs hashed; active pairs have complete native 512 windows; official-label masks rasterized without geometry repair')
if __name__=='__main__':run()

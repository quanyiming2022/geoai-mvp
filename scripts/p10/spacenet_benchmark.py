"""Offline official-GT P10 pilot; never writes platform resources or model code.
prepare freezes inputs before any predictions; run requires explicit worker env;
report uses fixed threshold 0.5 and preserves empty-GT undefined scores.
"""
import argparse,base64,csv,hashlib,json,math,os,sys,time
from pathlib import Path
from uuid import UUID,uuid4
import httpx,numpy as np,rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.windows import Window
from rasterio.warp import transform_geom
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/api'))
from geoai.native_tile import _rgb
from geoai.worker_contract import ImagePayload,ModelWorkerRequest,ModelWorkerResponse
from metrics import summarize,difference
DATA=Path('/Volumes/Extreme SSD/数据集/SpaceNet2_P10_subset')
OUT=ROOT/'artifacts/p10/spacenet-gt-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def png(p,a):
 a=np.asarray(a,dtype='uint8');a=a[None] if a.ndim==2 else a
 with rasterio.open(p,'w',driver='PNG',width=a.shape[2],height=a.shape[1],count=a.shape[0],dtype='uint8') as d:d.write(a)
def tif(p,a,crs,transform):
 a=np.asarray(a);a=a[None] if a.ndim==2 else a
 with rasterio.open(p,'w',driver='GTiff',width=a.shape[2],height=a.shape[1],count=a.shape[0],dtype=a.dtype,crs=crs,transform=transform,compress='deflate') as d:d.write(a)
def areas(transform,height=512,width=512):
 # WGS84 ellipsoid surface integral for geographic lat/lon pixel rectangles.
 a=6378137.;e2=6.6943799901413165e-3;e=math.sqrt(e2)
 def f(lat):
  u=np.sin(np.deg2rad(lat));return u/(2*(1-e2*u*u))+np.arctanh(e*u)/(2*e)
 lat=transform.f+np.arange(height+1)*transform.e
 row=np.abs(np.diff(f(lat)))*abs(math.radians(transform.a))*a*a*(1-e2)
 return np.repeat(row[:,None],width,axis=1)
def ranges(ds):
 # Exact existing production convert() display-range policy; no new normalization.
 scale=min(1,256/max(ds.width,ds.height));h,w=round(ds.height*scale),round(ds.width*scale)
 data=ds.read([1,2,3],out_shape=(3,h,w),resampling=Resampling.bilinear);alpha=ds.dataset_mask(out_shape=(h,w));result=[]
 for band in data:
  v=band[(alpha>0)&np.isfinite(band)];lo,hi=(0,255) if data.dtype==np.uint8 else np.percentile(v,[2,98])
  if lo==hi:lo,hi=lo-.5,hi+.5
  result.append([float(lo),float(hi)])
 return result

def prepare():
 OUT.mkdir(exist_ok=False,parents=True)
 manifest=json.loads((DATA/'manifest.json').read_text());validation=json.loads((DATA/'validation.json').read_text())
 queries=[];geoms={}
 for pair in manifest['pairs']:
  if not pair.get('selected_for_p10',True):continue
  for o in pair['objects']:assert sha(DATA/o['file'])==o['sha256']
  source=next(DATA/o['file'] for o in pair['objects'] if o['file'].endswith('.tif'))
  label=next(DATA/o['file'] for o in pair['objects'] if o['file'].endswith('.geojson'))
  city='Shanghai' if 'Shanghai' in pair['city'] else 'LasVegas';image=source.stem.split('_PS-RGB_')[-1];qid=f'{city}-{image}'
  folder=OUT/'inputs'/qid;folder.mkdir(parents=True)
  labeldata=json.loads(label.read_text());labelcrs=labeldata.get('crs',{}).get('properties',{}).get('name','EPSG:4326')
  with rasterio.open(source) as ds:
   assert str(ds.crs)=='EPSG:4326' and ds.width==650 and ds.height==650 and ds.count==3
   assert ds.transform.b==ds.transform.d==0 and ds.transform.a>0 and ds.transform.e<0
   gs=[transform_geom(labelcrs,ds.crs,f['geometry']) for f in labeldata['features'] if f.get('geometry')]
   full=rasterize([(g,1) for g in gs],out_shape=(650,650),transform=ds.transform,dtype='uint8') if gs else np.zeros((650,650),dtype='uint8')
   with rasterio.open(DATA/pair['city']/'derived'/image/'building_gt.tif') as prior:
    assert prior.crs==ds.crs and prior.transform==ds.transform and prior.shape==ds.shape
    assert np.array_equal(full,prior.read(1)),'Stored GT differs from official polygon rasterization'
   win=Window(69,69,512,512);aff=ds.window_transform(win);display=ranges(ds);rgb=_rgb(ds,win,display)
   valid=(ds.dataset_mask(window=win)>0)&np.any(ds.read([1,2,3],window=win)>0,axis=0);assert valid.all()
   gt=full[69:581,69:581];assert gt.shape==(512,512)
   png(folder/'query.png',rgb);png(folder/'gt.png',gt*255);tif(folder/'gt.tif',gt,ds.crs,aff);tif(folder/'query.tif',rgb,ds.crs,aff);png(folder/'valid_mask.png',valid*255)
   overlay=rgb.copy();overlay[:,gt>0]=(.6*rgb[:,gt>0]+.4*np.array([255,40,40])[:,None]).astype('uint8');png(folder/'gt-overlay.png',overlay)
   pixelareas=areas(aff);np.save(folder/'pixel_area_m2.npy',pixelareas)
   val=next(v for v in validation if v['city']==pair['city'] and v['image_id']==image)
   q={'query_id':qid,'city':city,'source_image':str(source.relative_to(DATA)),'source_sha256':sha(source),'label_sha256':sha(label),'window':[69,69,512,512],'crs':str(ds.crs),'transform':list(aff)[:6],'display_ranges':display,'gsd_xy_m':val['approx_center_gsd_m'],'gt_pixels':int(gt.sum()),'official_full_chip_buildings':len(gs),'scene_type':'negative' if not gt.any() else 'building_containing','valid_pixels':int(valid.sum()),'analysis_area_m2':float(pixelareas.sum()),'requested_scale_checks':{str(g):{'available':False,'reason':'512 target pixels exceed original chip physical footprint','required_m':512*g,'available_approx_m':[650*x for x in val['approx_center_gsd_m']]} for g in [1.,1.5,2.]}}
   for v in q['requested_scale_checks'].values():assert min(v['available_approx_m'])<v['required_m']
   queries.append(q);geoms[qid]=gs;dump(folder/'input-metadata.json',q)
 # Preregister supports by chip and deterministic moderate polygon area, never predictions.
 chosen=[('SN2-building-01','Shanghai-img1007'),('SN2-building-02','Shanghai-img1708'),('SN2-building-03','LasVegas-img2529')]
 supports=[]
 for sid,qid in chosen:
  q=next(q for q in queries if q['query_id']==qid);folder=OUT/'supports'/sid;folder.mkdir(parents=True)
  with rasterio.open(OUT/'inputs'/qid/'query.tif') as ds:
   candidates=[]
   for index,g in enumerate(geoms[qid]):
    mask=rasterize([(g,1)],out_shape=(512,512),transform=ds.transform,dtype='uint8');ys,xs=np.where(mask)
    if 200<=mask.sum()<=5000 and len(xs) and min(xs.min(),ys.min())>=8 and max(xs.max(),ys.max())<504:
     candidates.append((abs(math.log(float(mask.sum())/1200)),index,mask))
   assert candidates,f'No moderate complete support polygon {qid}'
   _,index,mask=min(candidates,key=lambda x:(x[0],x[1]));rgb=ds.read()
  (folder/'support.png').write_bytes((OUT/'inputs'/qid/'query.png').read_bytes());png(folder/'support_mask.png',mask*255)
  overlay=rgb.copy();overlay[:,mask>0]=(.5*rgb[:,mask>0]+.5*np.array([255,40,40])[:,None]).astype('uint8');png(folder/'overlay.png',overlay)
  supports.append({'support_id':sid,'query_id':qid,'city':q['city'],'prompt_type':'building','official_feature_index':index,'mask_pixels':int(mask.sum()),'gsd_xy_m':q['gsd_xy_m'],'selection':'minimum abs(log(area_pixels/1200)); 200..5000 px; >=8px border; frozen before inference'})
 for sid,qid in [('SN2-wrong-Shanghai','Shanghai-img1001'),('SN2-wrong-LasVegas','LasVegas-img1002')]:
  q=next(q for q in queries if q['query_id']==qid);assert q['gt_pixels']==0
  folder=OUT/'supports'/sid;folder.mkdir(parents=True);mask=np.zeros((512,512),dtype='uint8');mask[232:280,232:280]=1
  (folder/'support.png').write_bytes((OUT/'inputs'/qid/'query.png').read_bytes());png(folder/'support_mask.png',mask*255)
  with rasterio.open(folder/'support.png') as ds:rgb=ds.read()
  rgb[:,mask>0]=(.5*rgb[:,mask>0]+.5*np.array([255,40,40])[:,None]).astype('uint8');png(folder/'overlay.png',rgb)
  supports.append({'support_id':sid,'query_id':qid,'city':q['city'],'prompt_type':'nonbuilding_control','mask_pixels':int(mask.sum()),'gsd_xy_m':q['gsd_xy_m'],'selection':'fixed central 48x48 rectangle on official zero-building chip; visual review required'})
 config={'version':'spacenet-gt-v1','seed':42,'slot_id':24,'primary_threshold':.5,'gt_policy':'official SpaceNet2 human building polygons, pixel-center rasterization; full query GT; no own accuracy labels invented','rgb_policy':'existing raster_processing.convert thumbnail percentile display ranges + unchanged native_tile._rgb; no prediction-based tuning','queries':queries,'supports':supports,'experiments':40,'source_manifest_sha256':sha(DATA/'manifest.json'),'limitations':['convenience pilot, training-set provenance/pretraining overlap unknown','same-scene explicitly separated from held-out chip/city','native geographic grids have anisotropic physical GSD','1/1.5/2m 512 grids unavailable; no padding or artificial resize']}
 dump(OUT/'config.json',config)
 dump(OUT/'input-sha256.json',{str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()})
 html='<meta charset="utf-8"><title>P10 frozen supports</title><style>body{font:14px sans-serif;background:#20282b;color:white}section{display:inline-block;margin:10px}img{width:400px}</style>'
 for s in supports:html+=f'<section><h3>{s["support_id"]} · {s["query_id"]}</h3><img src="supports/{s["support_id"]}/overlay.png"></section>'
 (OUT/'support-review.html').write_text(html)
 print('PREPARED: 8 queries, 3 building supports, 2 wrong supports, 40 frozen comparisons; visual review before run')

def check_inputs():
 for name,digest in json.loads((OUT/'input-sha256.json').read_text()).items():assert sha(OUT/name)==digest,name
 baseline=json.loads((ROOT/'artifacts/p10/baseline-manifest.json').read_text())
 for name,digest in baseline['sha256'].items():assert sha(ROOT/name)==digest,name
 return baseline

def run():
 baseline=check_inputs();config=json.loads((OUT/'config.json').read_text());resultdir=OUT/'runs';resultdir.mkdir(exist_ok=False)
 assert (OUT/'visual-review.json').exists(),'Review supports before inference'
 records=[]
 with httpx.Client(base_url=os.environ['P10_WORKER_URL'],timeout=180,trust_env=False) as client:
  info=client.get('/model-info').raise_for_status().json()
  for k in ['checkpoint_digest','git_commit','model_version','usage_policy']:assert info[k]==baseline['worker'][k],k
  dump(OUT/'worker-before.json',info)
  for q in config['queries']:
   queryfolder=OUT/'inputs'/q['query_id']
   with rasterio.open(queryfolder/'gt.tif') as ds:gt=ds.read(1)>0;aff=ds.transform;crs=ds.crs
   pa=np.load(queryfolder/'pixel_area_m2.npy')
   for s in config['supports']:
    folder=resultdir/(q['query_id']+'__'+s['support_id']);folder.mkdir();sf=OUT/'supports'/s['support_id']
    for name,src in [('support.png',sf/'support.png'),('support_mask.png',sf/'support_mask.png'),('query.png',queryfolder/'query.png'),('gt.png',queryfolder/'gt.png')]: (folder/name).write_bytes(src.read_bytes())
    def payload(n):return ImagePayload(data=base64.b64encode((folder/n).read_bytes()).decode())
    req=ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=UUID(os.environ['P10_RELEASE_ID']),support_image=payload('support.png'),support_mask=payload('support_mask.png'),query_image=payload('query.png'),seed=config['seed'])
    start=time.monotonic();res=ModelWorkerResponse.model_validate(client.post('/v1/inference/oneshot-segmentation',json=req.model_dump(mode='json')).raise_for_status().json());wall=(time.monotonic()-start)*1000
    assert res.checkpoint_digest==info['checkpoint_digest'] and res.metadata.get('slot_id')==24
    p=res.probabilities();np.save(folder/'probability.npy',p);tif(folder/'probability.tif',p,crs,aff)
    for t in [.3,.5,.7]:png(folder/f'pred_{int(10*t):02d}.png',(p>=t)*255)
    with rasterio.open(queryfolder/'query.tif') as ds:rgb=ds.read()
    pred=p>=.5;overlay=rgb.copy()
    # TP green, FP red, FN blue; original GT remains separate.
    for mask,color in [(pred&gt,[30,230,80]),(pred&~gt,[255,40,40]),(~pred&gt,[40,120,255])]:overlay[:,mask]=(.55*rgb[:,mask]+.45*np.array(color)[:,None]).astype('uint8')
    png(folder/'overlay.png',overlay)
    m=summarize(p,pixel_area=float(pa.mean()),gt=gt,gt_approved=True)
    m.update(false_positive_area=float(pa[pred&~gt].sum()),predicted_area_m2=float(pa[pred].sum()),gt_area_m2=float(pa[gt].sum()),gt_status='official_human_building_annotation')
    relation='same_scene' if s['query_id']==q['query_id'] else ('intra_city_cross_tile' if s['city']==q['city'] else 'cross_city')
    row={'experiment_id':folder.name,'support_id':s['support_id'],'query_id':q['query_id'],'support_city':s['city'],'query_city':q['city'],'relation':relation,'support_gsd':s['gsd_xy_m'],'query_gsd':q['gsd_xy_m'],'scene_type':q['scene_type'],'prompt_type':s['prompt_type'],'seed':42,'slot_id':24,'model_version':res.model_version,'checkpoint_digest':res.checkpoint_digest,'model_git_commit':info['git_commit'],'runtime_ms':res.runtime_ms,'http_wall_ms':wall,'peak_gpu_memory_mb':res.metadata.get('gpu_memory_peak')/1024**2 if res.metadata.get('gpu_memory_peak') is not None else None,'worker_metadata':res.metadata,**m}
    dump(folder/'metadata.json',row);records.append(row);print(folder.name,'F1',row['F1'],'IoU',row['IoU'],flush=True)
  dump(OUT/'worker-after.json',client.get('/model-info').raise_for_status().json())
 check_inputs();dump(OUT/'summary.json',records);print('COMPLETE: 40 real frozen-checkpoint official-GT predictions',flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);args=parser.parse_args();globals()[args.action]()

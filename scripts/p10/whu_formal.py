"""P10 offline WHU formal GT protocol. No platform or frozen model modifications."""
import sys,json,hashlib,base64,os,time,csv
from pathlib import Path
from uuid import UUID,uuid4
import numpy as np,rasterio,shapefile,httpx
from rasterio.features import rasterize,shapes
from rasterio.warp import reproject,Resampling
from affine import Affine
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'services/api'))
from geoai.worker_contract import ModelWorkerRequest,ModelWorkerResponse,ImagePayload
from metrics import summarize,difference
from io_utils import png,tif
D=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'));O=ROOT/'artifacts/p10/whu-formal-v1'
G=[1.,1.5,2.,3.,4.]
def dump(p,a):Path(p).write_text(json.dumps(a,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def audit():
 for r in json.loads((D/'sha256-manifest.json').read_text()):assert sha(D/r['path'])==r['sha256'],r['path']
 b=json.loads((ROOT/'artifacts/p10/baseline-manifest.json').read_text())
 for p,h in b['sha256'].items():assert sha(ROOT/p)==h,p
 return b

def prepare():
 audit();O.mkdir(parents=True,exist_ok=False);queries=[];supports=[];check=[];features={};sources={}
 for region in ['urban','outskirts']:
  folder=D/'aerial'/f'christchurch-{region}';ds=rasterio.open(folder/'image_0p3m.tif');sources[region]=ds
  ff=[s.__geo_interface__ for s in shapefile.Reader(str(folder/'buildings.shp')).iterShapes()];features[region]=ff
  with rasterio.open(folder/'building_gt_0p3m.tif') as gt:
   assert ds.crs==gt.crs and ds.transform==gt.transform and ds.shape==gt.shape and ds.bounds==gt.bounds
   original=rasterize([(g,1) for g in ff],out_shape=ds.shape,transform=ds.transform,dtype='uint8');assert np.array_equal(original,gt.read(1));assert np.array_equal(ds.dataset_mask(),gt.dataset_mask())
  check.append({'dataset':region,'crs':str(ds.crs),'transform':list(ds.transform)[:6],'shape':list(ds.shape),'extent':list(ds.bounds),'gt_extent_equal':True,'gt_pixel_equality':True,'valid_mask_equal':True})
 def build(region,cx,cy,g,ident,geom=None):
  ds=sources[region];t=Affine(g,0,cx-256*g,0,-g,cy+256*g)
  assert t.c>=ds.bounds.left-1e-7 and t.c+512*g<=ds.bounds.right+1e-7 and t.f<=ds.bounds.top+1e-7 and t.f-512*g>=ds.bounds.bottom-1e-7
  folder=O/'inputs'/ident;folder.mkdir(parents=True);rgb=np.zeros((3,512,512),dtype='uint8')
  for b in range(1,4):reproject(rasterio.band(ds,b),rgb[b-1],dst_transform=t,dst_crs=ds.crs,resampling=Resampling.bilinear)
  valid=np.zeros((512,512),dtype='uint8');reproject(ds.dataset_mask(),valid,src_transform=ds.transform,src_crs=ds.crs,dst_transform=t,dst_crs=ds.crs,resampling=Resampling.nearest)
  gt=rasterize([(f,1) for f in features[region]],out_shape=(512,512),transform=t,dtype='uint8')
  tif(folder/'rgb.tif',rgb,ds.crs,t);tif(folder/'gt.tif',gt,ds.crs,t);tif(folder/'valid.tif',valid,ds.crs,t);png(folder/'rgb.png',rgb);png(folder/'gt.png',gt*255)
  if geom:
   mask=rasterize([(geom,1)],out_shape=(512,512),transform=t,dtype='uint8')*(valid>0);assert mask.sum()>0,ident
   png(folder/'mask.png',mask*255);overlay=rgb.copy();overlay[:,mask>0]=(.5*rgb[:,mask>0]+.5*np.array([255,40,40])[:,None]).astype('uint8');png(folder/'overlay.png',overlay)
  return {'id':ident,'region':region,'gsd':g,'crs':str(ds.crs),'transform':list(t)[:6],'center':[cx,cy],'valid_pixels':int((valid>0).sum()),'gt_pixels':int(gt.sum()),'mask_pixels':int(mask.sum()) if geom else None,'GSD_METADATA_CONFLICT':False}
 for region,ds in sources.items():
  cx,cy=ds.transform*(ds.width/2,ds.height/2)
  for pos,(dx,dy) in enumerate([(-80,-80),(80,80)],1):
   for g in G:queries.append(build(region,cx+dx,cy+dy,g,f'Q-{region}-{pos}-{g:g}m'))
 # Freeze aerial prompts from native GT, without querying the model.
 ds=sources['urban'];cx,cy=ds.transform*(3840,3840);candidates=[]
 for i,f in enumerate(features['urban']):
  rings=f['coordinates'] if f['type']=='Polygon' else [r for p in f['coordinates'] for r in p]
  coords=np.concatenate([np.asarray(r)[:,:2] for r in rings]);x,y=coords.mean(0)
  if abs(x-cx)>200 or abs(y-cy)>200:continue
  t=Affine(1,0,x-256,0,-1,y+256);mask=rasterize([(f,1)],out_shape=(512,512),transform=t,dtype='uint8');area=int(mask.sum())
  if area>=100:candidates.append((area,i,x,y,f))
 assert candidates
 used=set();selected=[]
 for name,target,kind in [('P1',1800,'large'),('P2',350,'medium_independent'),('P3',160,'dense_environment')]:
  options=[r for r in candidates if r[1] not in used];area,i,x,y,f=min(options,key=lambda r:abs(np.log(r[0]/target)));used.add(i);selected.append({'id':name,'feature_index':i,'area_at_1m':area,'kind':kind,'geometry':f})
  # All support grids use a shared source center; same target is present at every GSD.
  for g in G:
   row=build('urban',cx,cy,g,f'{name}-{g:g}m',f);row.update(prompt=name,prompt_type='building',morphology=kind,official_feature_index=i);supports.append(row)
 # Fixed world rectangles, selected from the visually inspected field/vegetation region.
 ds=sources['outskirts'];ox,oy=ds.transform*(3840,3840)
 for name,dx,dy in [('W-vegetation',-100,80),('W-field',90,110)]:
  x,y=ox+dx,oy+dy;f={'type':'Polygon','coordinates':[[[x-15,y-15],[x+15,y-15],[x+15,y+15],[x-15,y+15],[x-15,y-15]]]}
  for g in G:
   row=build('outskirts',ox,oy,g,f'{name}-{g:g}m',f)
   with rasterio.open(O/'inputs'/row['id']/'gt.tif') as gt,rasterio.open(O/'inputs'/row['id']/'rgb.tif') as im,rasterio.open(O/'inputs'/row['id']/'mask.png') as ma:assert not ((gt.read(1)>0)&(ma.read(1)>0)).any()
   row.update(prompt=name,prompt_type='wrong',geometry=f);supports.append(row)
 # Satellite geometry is used for alignment only; no absolute area/GSD inference.
 for name in ['42','43','1551','3725']:
  folder=D/'satellite-ii/georeferenced'/name;ident=f'SAT-{name}';out=O/'inputs'/ident;out.mkdir(parents=True)
  with rasterio.open(folder/'image.tif') as ds,rasterio.open(folder/'building_gt.tif') as gt:
   assert ds.crs==gt.crs and ds.transform==gt.transform and ds.bounds==gt.bounds and ds.shape==gt.shape
   a=ds.read();truth=gt.read(1)
   with rasterio.open(D/'satellite-ii/image'/f'{name}.tif') as orig,rasterio.open(D/'satellite-ii/label'/f'{name}.tif') as label:assert np.array_equal(a,orig.read()) and np.array_equal(truth>0,label.read(1)>0)
   tif(out/'rgb.tif',a,ds.crs,ds.transform);tif(out/'gt.tif',truth,ds.crs,ds.transform);tif(out/'valid.tif',np.full((512,512),255,dtype='uint8'),ds.crs,ds.transform);png(out/'rgb.png',a);png(out/'gt.png',truth*255)
   row={'id':ident,'region':'satellite','scene':name,'gsd':None,'crs':str(ds.crs),'transform':list(ds.transform)[:6],'valid_pixels':512**2,'gt_pixels':int((truth>0).sum()),'GSD_METADATA_CONFLICT':True};queries.append(row);check.append({**row,'gt_pixel_equality':True,'source_pixels_unchanged':True})
   if name in ['42','1551']:
    options=[]
    for f,v in shapes(truth.astype('uint8'),transform=ds.transform):
     if not v:continue
     mask=rasterize([(f,1)],out_shape=(512,512),transform=ds.transform,dtype='uint8');ys,xs=np.where(mask)
     if xs.min()>5 and xs.max()<506 and ys.min()>5 and ys.max()<506:options.append((abs(np.log(mask.sum()/1500)),mask,f))
    _,mask,f=min(options,key=lambda x:x[0]);png(out/'mask.png',mask*255);over=a.copy();over[:,mask>0]=(.5*a[:,mask>0]+.5*np.array([255,40,40])[:,None]).astype('uint8');png(out/'overlay.png',over)
    supports.append({**row,'prompt':f'S-{name}','prompt_type':'building','geometry':f})
 # Satellite controls: fixed GT-free 32px squares nearest center (deterministic, no output inspection).
 for name in ['43','3725']:
  base=next(q for q in queries if q['id']==f'SAT-{name}');ident=f'SW-{name}';dest=O/'inputs'/ident;dest.mkdir()
  for fn in ['rgb.png','rgb.tif','gt.tif','valid.tif']: (dest/fn).write_bytes((O/'inputs'/base['id']/fn).read_bytes())
  with rasterio.open(dest/'gt.tif') as ds:truth=ds.read(1)
  pos=[(abs(x-240)+abs(y-240),x,y) for y in range(32,449,32) for x in range(32,449,32) if not truth[y:y+32,x:x+32].any()];_,x,y=min(pos);mask=np.zeros((512,512),dtype='uint8');mask[y:y+32,x:x+32]=255;png(dest/'mask.png',mask)
  supports.append({**base,'id':ident,'prompt':ident,'prompt_type':'wrong'})
 # Common 512m evaluation core at 1m, shared valid pixels across all five GSDs.
 for region in sources:
  for pos in [1,2]:
   ref=next(q for q in queries if q['id']==f'Q-{region}-{pos}-1m');t=Affine(*ref['transform']);shared=np.ones((512,512),dtype=bool)
   for q in [q for q in queries if q['id'].startswith(f'Q-{region}-{pos}-')]:
    with rasterio.open(O/'inputs'/q['id']/'valid.tif') as ds:
     m=np.zeros((512,512),dtype='uint8');reproject(ds.read(1),m,src_transform=ds.transform,src_crs=ds.crs,dst_transform=t,dst_crs=ds.crs,resampling=Resampling.nearest);shared&=m>0
   png(O/'inputs'/ref['id']/'common_valid.png',shared*255)
 runs=[]
 for q in queries:
  if q['region']!='satellite':
   eligible=[s for s in supports if s['region']!='satellite' and (s['gsd']==q['gsd'] or s['prompt_type']=='building' and (s['gsd']==1 or s['gsd']==2 and q['gsd']==1))]
  else:eligible=[s for s in supports if s['region']=='satellite']+[next(s for s in supports if s['id']=='P1-1m')]
  for s in eligible:runs.append({'query':q['id'],'support':s['id']})
 config={'seed':42,'slot_id':24,'threshold':.5,'queries':queries,'supports':supports,'runs':runs,'selected_aerial_features':selected,'caveats':['two overlapping positions per region are not independent samples','five GSDs alter support/query FOV; common-core measures accompany full-window scores','satellite absolute GSD/area withheld: GSD_METADATA_CONFLICT','official training data: pretraining overlap unknown','official footprint GT, potential roof displacement; no GT modification'], 'status':'inputs frozen before inference'}
 dump(O/'config.json',config);dump(O/'geometry-audit.json',check)
 dump(O/'input-sha256.json',{str(p.relative_to(O)):sha(p) for p in O.rglob('*') if p.is_file()})
 print('PREPARED',len(runs),'experiments',[(r['id'],r['area_at_1m'],r['feature_index']) for r in selected],flush=True)

def run():
 baseline=audit();c=json.loads((O/'config.json').read_text())
 for name,h in json.loads((O/'input-sha256.json').read_text()).items():assert sha(O/name)==h
 assert (O/'visual-review.json').exists()
 records=[];client=httpx.Client(base_url=os.environ['P10_WORKER_URL'],timeout=180,trust_env=False);info=client.get('/model-info').raise_for_status().json()
 for k in ['checkpoint_digest','git_commit','model_version','usage_policy']:assert info[k]==baseline['worker'][k],k
 dump(O/'worker-before.json',info)
 for i,exp in enumerate(c['runs']):
  q=next(x for x in c['queries'] if x['id']==exp['query']);s=next(x for x in c['supports'] if x['id']==exp['support']);name=q['id']+'__'+s['id'];folder=O/'runs'/name
  if (folder/'metadata.json').exists():records.append(json.loads((folder/'metadata.json').read_text()));continue
  folder.mkdir(parents=True,exist_ok=True)
  for dst,src in [('query.png',O/'inputs'/q['id']/'rgb.png'),('gt.png',O/'inputs'/q['id']/'gt.png'),('support.png',O/'inputs'/s['id']/'rgb.png'),('support_mask.png',O/'inputs'/s['id']/'mask.png')]: (folder/dst).write_bytes(src.read_bytes())
  # Preview mask is 0/255; frozen Worker contract requires lossless 0/1 transport.
  with rasterio.open(O/'inputs'/s['id']/'mask.png') as mask_ds:transport_mask=(mask_ds.read(1)>0).astype('uint8')
  png(folder/'support_mask.png',transport_mask)
  def payload(n):return ImagePayload(data=base64.b64encode((folder/n).read_bytes()).decode())
  req=ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=UUID(os.environ['P10_RELEASE_ID']),support_image=payload('support.png'),support_mask=payload('support_mask.png'),query_image=payload('query.png'),seed=42)
  start=time.monotonic();res=ModelWorkerResponse.model_validate(client.post('/v1/inference/oneshot-segmentation',json=req.model_dump(mode='json')).raise_for_status().json());p=res.probabilities();assert res.checkpoint_digest==info['checkpoint_digest'] and res.metadata.get('slot_id')==24
  np.save(folder/'probability.npy',p);tif(folder/'probability.tif',p,q['crs'],Affine(*q['transform']))
  with rasterio.open(O/'inputs'/q['id']/'gt.tif') as ds:gt=ds.read(1)>0
  with rasterio.open(O/'inputs'/q['id']/'valid.tif') as ds:valid=ds.read(1)>0
  with rasterio.open(O/'inputs'/q['id']/'rgb.tif') as ds:rgb=ds.read()
  m=summarize(p,pixel_area=q['gsd']**2 if q['gsd'] else 1,gt=gt,valid=valid,gt_approved=True);m['false_negative_area']=m['FN']*q['gsd']**2 if q['gsd'] else None
  if not q['gsd']:m['false_positive_area']=None
  m['gt_status']='official_human_vectors';m['area_units']='m2' if q['gsd'] else 'withheld_metadata_conflict'
  common=None
  if q['gsd']:
   refid=q['id'].rsplit('-',1)[0]+'-1m';ref=next(x for x in c['queries'] if x['id']==refid)
   pp=np.zeros((512,512),dtype='float32');reproject(p,pp,src_transform=Affine(*q['transform']),src_crs=q['crs'],dst_transform=Affine(*ref['transform']),dst_crs=ref['crs'],resampling=Resampling.bilinear)
   with rasterio.open(O/'inputs'/refid/'gt.tif') as d:gg=d.read(1)>0
   with rasterio.open(O/'inputs'/refid/'common_valid.png') as d:vv=d.read(1)>0
   common=summarize(pp,pixel_area=1,gt=gg,valid=vv,gt_approved=True);common['false_negative_area']=common['FN'];np.save(folder/'common_core_probability.npy',pp)
  pred=p>=.5
  for t in [.3,.5,.7]:png(folder/f'pred_{int(t*10):02d}.png',(p>=t)*255)
  overlay=rgb.copy()
  for mask,color in [(pred&gt&valid,[30,230,80]),(pred&~gt&valid,[255,40,40]),(~pred&gt&valid,[40,120,255])]:overlay[:,mask]=(.55*rgb[:,mask]+.45*np.array(color)[:,None]).astype('uint8')
  png(folder/'overlay.png',overlay)
  row={'experiment_id':name,'query_id':q['id'],'support_id':s['id'],'prompt':s['prompt'],'prompt_type':s['prompt_type'],'query_region':q['region'],'support_region':s['region'],'support_gsd':s['gsd'],'query_gsd':q['gsd'],'GSD_METADATA_CONFLICT':q['GSD_METADATA_CONFLICT'],'seed':42,'slot_id':24,'checkpoint_digest':res.checkpoint_digest,'model_version':res.model_version,'model_git_commit':info['git_commit'],'runtime_ms':res.runtime_ms,'wall_ms':(time.monotonic()-start)*1000,'peak_gpu_memory_mb':res.metadata.get('gpu_memory_peak')/1024**2 if res.metadata.get('gpu_memory_peak') is not None else None,'worker_metadata':res.metadata,'common_core':common,**m}
  dump(folder/'metadata.json',row);records.append(row);print(i+1,len(c['runs']),name,'F1',m['F1'],flush=True)
 dump(O/'summary.json',records);dump(O/'worker-after.json',client.get('/model-info').raise_for_status().json());audit();print('COMPLETE',len(records),flush=True)
if __name__=='__main__':globals()[sys.argv[1]]()

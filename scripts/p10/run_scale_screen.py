"""Preliminary A/B/C scale screen; original approved support unchanged on disk."""
import base64,hashlib,json,os,sys,time
from pathlib import Path
from uuid import uuid4,UUID
import httpx,numpy as np,rasterio
from affine import Affine
from rasterio.warp import reproject,Resampling
from resample import grid_for,rgb_grid
from metrics import summarize
from run_fixed_prompt_diagnostics import ROOT,png
from geoai.worker_contract import ModelWorkerRequest,ModelWorkerResponse,ImagePayload

def run():
 root=ROOT/'artifacts/p10';out=root/'scale-screen';out.mkdir(exist_ok=False)
 source=root/'sources/SPOT6_RVB_1M00_2019_10014.tif';baseline=ROOT/'artifacts/p9b-building/registered-run';a=next(baseline.glob('A-*'));manifest=json.loads((baseline/'fixtures.json').read_text());fixture=next(v for k,v in manifest['fixtures'].items() if k.startswith('A-'))
 with rasterio.open(a/'support_mask.png') as ds:mask=ds.read(1)
 # P9B support and A query share the same fixed native grid.
 original_transform=Affine(*fixture['transform'])
 with rasterio.open(source) as ds:
  for g in (1.,1.5,2.):
   folder=out/f'support-{g:g}m';folder.mkdir()
   if g==1.:
    for n in ('support.png','support_mask.png'):(folder/n).write_bytes((a/n).read_bytes())
    t=original_transform
   else:
    t=grid_for(ds,730+256,715+256,g);rgb=rgb_grid(ds,t);target=np.zeros((512,512),dtype='uint8')
    reproject(mask,target,src_transform=original_transform,src_crs=ds.crs,dst_transform=t,dst_crs=ds.crs,resampling=Resampling.nearest)
    png(folder/'support.png',rgb);png(folder/'support_mask.png',target)
   (folder/'metadata.json').write_text(json.dumps({'gsd':g,'transform':list(t)[:6],'crs':str(ds.crs),'annotation':'resampling of frozen approved building-01 support, NOT query GT'},indent=2))
 rows=[];config=[{'query':q,'support_gsd':s,'query_gsd':g} for q in ['Q14','Q15','Q07'] for s,g in [(1,2),(2,2),(2,1),(1.5,1.5)]]
 (out/'config.json').write_text(json.dumps(config,indent=2))
 expected=json.loads((root/'baseline-manifest.json').read_text())['worker']
 with httpx.Client(base_url=os.environ['P10_WORKER_URL'],timeout=180,trust_env=False) as client:
  assert client.get('/model-info').raise_for_status().json()['checkpoint_digest']==expected['checkpoint_digest']
  for case in config:
   q,s,g=case['query'],case['support_gsd'],case['query_gsd'];folder=out/f'{q}-{s:g}to{g:g}';folder.mkdir();support=out/f'support-{s:g}m'
   for n in ('support.png','support_mask.png'):(folder/n).write_bytes((support/n).read_bytes())
   with rasterio.open(root/f'scale-grids/{q}-{g:g}m.tif') as ds:rgb=ds.read();t=ds.transform;crs=ds.crs
   png(folder/'query.png',rgb)
   def payload(n):return ImagePayload(data=base64.b64encode((folder/n).read_bytes()).decode())
   req=ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=UUID(os.environ['P10_RELEASE_ID']),support_image=payload('support.png'),support_mask=payload('support_mask.png'),query_image=payload('query.png'),seed=42)
   result=ModelWorkerResponse.model_validate(client.post('/v1/inference/oneshot-segmentation',json=req.model_dump(mode='json')).raise_for_status().json());assert result.checkpoint_digest==expected['checkpoint_digest'];p=result.probabilities();np.save(folder/'probability.npy',p)
   with rasterio.open(folder/'probability.tif','w',driver='GTiff',width=512,height=512,count=1,dtype='float32',crs=crs,transform=t,compress='deflate') as dst:dst.write(p,1)
   for threshold in (.3,.5,.7):png(folder/f'pred_{int(threshold*10):02d}.png',(p>=threshold)*255)
   pred=p>=.5;rgb[:,pred]=(.6*rgb[:,pred]+.4*np.array([255,30,30])[:,None]).astype('uint8');png(folder/'overlay.png',rgb)
   r={'experiment_id':folder.name,'support_id':'building-01','query_id':q,'support_gsd':s,'query_gsd':g,'prompt_type':'building','scene_type':{'Q14':'same-region','Q15':'distant-tile','Q07':'farmland-candidate'}[q],'seed':42,'slot_id':result.metadata.get('slot_id'),'runtime_ms':result.runtime_ms,'peak_gpu_memory_mb':result.metadata.get('gpu_memory_peak')/1024**2 if result.metadata.get('gpu_memory_peak') is not None else None,'checkpoint_digest':result.checkpoint_digest,'model_version':result.model_version,'model_git_commit':expected['git_commit'],'query_transform':list(t)[:6],'worker_metadata':result.metadata,'physical_extent_caveat':'Larger GSD covers larger scene; source-edge shifts are recorded in transform.',**summarize(p,pixel_area=g*g)}
   (folder/'metadata.json').write_text(json.dumps(r,indent=2));rows.append(r);print(folder.name,r['prob_mean'],flush=True)
 (out/'summary.json').write_text(json.dumps(rows,indent=2));print('COMPLETE: 12 preliminary scale runs, no GT accuracy')
if __name__=='__main__':run()

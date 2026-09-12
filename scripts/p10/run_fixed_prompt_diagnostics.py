"""P10 preliminary raw-response screen. No GT scores, no change to model inputs.
Requires P10_WORKER_URL and P10_RELEASE_ID. Refuses existing output directories.
"""
import base64,hashlib,json,os,sys,time
from pathlib import Path
from uuid import uuid4,UUID
import httpx,numpy as np,rasterio
from affine import Affine
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/api'))
from geoai.worker_contract import ModelWorkerRequest,ModelWorkerResponse,ImagePayload
from metrics import summarize,difference

def png(path,a):
 if a.ndim==2:a=a[None]
 with rasterio.open(path,'w',driver='PNG',width=a.shape[2],height=a.shape[1],count=a.shape[0],dtype='uint8') as dst:dst.write(a.astype('uint8'))

def run():
 root=ROOT/'artifacts/p10';out=root/'fixed-prompt-screen';out.mkdir(exist_ok=False)
 baseline=json.loads((root/'baseline-manifest.json').read_text());queries=json.loads((root/'candidate-manifest.json').read_text())
 supports={'building-01':ROOT/'artifacts/p9b-building/registered-run/A-same-image','vegetation-control':ROOT/'artifacts/p9b-building/registered-run/D-wrong-prompt'}
 # Locate frozen same-image directory without guessing its suffix.
 supports['building-01']=next((ROOT/'artifacts/p9b-building/registered-run').glob('A-*'))
 config={'stage':'preliminary_no_gt','seed':42,'primary_threshold':.5,'queries':queries,'supports':{k:{n:hashlib.sha256((v/n).read_bytes()).hexdigest() for n in ['support.png','support_mask.png']} for k,v in supports.items()}}
 (out/'config.json').write_text(json.dumps(config,indent=2));records=[];pairs=[]
 with httpx.Client(base_url=os.environ['P10_WORKER_URL'],timeout=180,trust_env=False) as client:
  info=client.get('/model-info').raise_for_status().json()
  assert all(info[k]==baseline['worker'][k] for k in ['checkpoint_digest','git_commit','model_version','usage_policy'])
  for q in queries:
   results={};source=root/'candidates'/q['query_id']
   for support_id,support in supports.items():
    folder=out/(q['query_id']+'-'+support_id);folder.mkdir()
    for dest,path in [('support.png',support/'support.png'),('support_mask.png',support/'support_mask.png'),('query.png',source/'query.png')]: (folder/dest).write_bytes(path.read_bytes())
    def payload(name):return ImagePayload(data=base64.b64encode((folder/name).read_bytes()).decode())
    request=ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=UUID(os.environ['P10_RELEASE_ID']),support_image=payload('support.png'),support_mask=payload('support_mask.png'),query_image=payload('query.png'),seed=42)
    started=time.monotonic();response=client.post('/v1/inference/oneshot-segmentation',json=request.model_dump(mode='json')).raise_for_status()
    result=ModelWorkerResponse.model_validate(response.json());assert result.checkpoint_digest==info['checkpoint_digest']
    p=result.probabilities();results[support_id]=p;np.save(folder/'probability.npy',p)
    with rasterio.open(folder/'probability.tif','w',driver='GTiff',width=512,height=512,count=1,dtype='float32',crs=q['crs'],transform=Affine(*q['transform']),compress='deflate') as dst:dst.write(p,1)
    for t in (.3,.5,.7):png(folder/f'pred_{int(t*10):02d}.png',(p>=t)*255)
    with rasterio.open(source/'query.tif') as ds:rgb=ds.read([1,2,3])
    pred=p>=.5;rgb[:,pred]=(.6*rgb[:,pred]+.4*np.array([255,30,30])[:,None]).astype('uint8');png(folder/'overlay.png',rgb)
    metadata={'experiment_id':folder.name,'support_id':support_id,'query_id':q['query_id'],'support_gsd':1.,'query_gsd':1.,'scene_type':q['scene_type_provisional'],'scene_classification_status':'unreviewed','prompt_type':'building' if support_id=='building-01' else 'wrong_vegetation','seed':42,'slot_id':result.metadata.get('slot_id'),'runtime_ms':result.runtime_ms,'http_wall_ms':1000*(time.monotonic()-started),'peak_gpu_memory_mb':result.metadata.get('gpu_memory_peak',0)/1024**2 if result.metadata.get('gpu_memory_peak') is not None else None,'model_version':result.model_version,'checkpoint_digest':result.checkpoint_digest,'model_git_commit':info['git_commit'],'worker_metadata':result.metadata,**summarize(p,pixel_area=1)}
    (folder/'metadata.json').write_text(json.dumps(metadata,indent=2));records.append(metadata);print(folder.name,metadata['prob_mean'],flush=True)
   pairs.append({'query_id':q['query_id'],**difference(results['building-01'],results['vegetation-control'])})
  assert client.get('/model-info').raise_for_status().json()['checkpoint_digest']==info['checkpoint_digest']
 (out/'summary.json').write_text(json.dumps(records,indent=2));(out/'prompt-differences.json').write_text(json.dumps(pairs,indent=2))
 print('COMPLETE: 32 raw-response runs; no GT accuracy or final capability verdict')
if __name__=='__main__':run()

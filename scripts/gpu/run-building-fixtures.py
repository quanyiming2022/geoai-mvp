import base64,json,os,sys,uuid,shutil
from pathlib import Path
import httpx,numpy as np,rasterio
from affine import Affine
sys.path.insert(0,str(Path.cwd()/'services/api'))
from geoai.worker_contract import ModelWorkerRequest,ModelWorkerResponse,ImagePayload
source=Path(os.environ.get('GEOAI_ACCEPTANCE_FIXTURES','artifacts/p9b-building'))
root=Path(os.environ['GEOAI_ACCEPTANCE_OUTPUT'])
root.mkdir(parents=True,exist_ok=False)
manifest=json.loads((source/'fixtures.json').read_text())
release_id=uuid.UUID(os.environ['GEOAI_ACCEPTANCE_MODEL_RELEASE_ID'])
endpoint_id=str(uuid.UUID(os.environ['GEOAI_ACCEPTANCE_ENDPOINT_ID']))
for name in manifest['fixtures']:
 (root/name).mkdir()
 for filename in ('support.png','support_mask.png','query.png','valid_mask.png','support-annotation-overlay.png'):
  shutil.copy(source/name/filename,root/name/filename)
manifest['annotation_method']='assistant visual digitization; roof and boundary explicitly approved by user'
(root/'fixtures.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
endpoint=os.environ['GEOAI_ACCEPTANCE_WORKER_URL'].rstrip('/')
summaries=[]
with httpx.Client(timeout=300,trust_env=False) as client:
 for name,fixture in manifest['fixtures'].items():
  folder=root/name
  def payload(n): return ImagePayload(data=base64.b64encode((folder/n).read_bytes()).decode())
  req=ModelWorkerRequest(job_id=uuid.uuid4(),attempt_id=uuid.uuid4(),model_release_id=release_id,support_image=payload('support.png'),support_mask=payload('support_mask.png'),query_image=payload('query.png'),seed=42)
  (folder/'transport-request.json').write_text(req.model_dump_json())
  response=client.post(endpoint+'/v1/inference/oneshot-segmentation',json=req.model_dump(mode='json'))
  (folder/'transport-response.json').write_text(response.text)
  response.raise_for_status(); result=ModelWorkerResponse.model_validate(response.json()); p=result.probabilities()
  np.save(folder/'probability.npy',p)
  with rasterio.open(folder/'probability.tif','w',driver='GTiff',width=512,height=512,count=1,dtype='float32',crs=fixture['crs'],transform=Affine(*fixture['transform']),compress='deflate') as dst: dst.write(p,1)
  mask=p>=.5
  with rasterio.open(folder/'prediction_mask.png','w',driver='PNG',width=512,height=512,count=1,dtype='uint8') as dst: dst.write(mask.astype('uint8')*255,1)
  with rasterio.open(folder/'query.png') as src: overlay=src.read()
  overlay[:,mask]=(.55*overlay[:,mask]+.45*np.array([255,60,40])[:,None]).astype('uint8')
  with rasterio.open(folder/'overlay.png','w',driver='PNG',width=512,height=512,count=3,dtype='uint8') as dst:dst.write(overlay)
  metrics={'fixture':name,'scope':'worker HTTP benchmark; not a persisted GeoAI Job','endpoint_id':endpoint_id,'model_release_id':str(release_id),'checkpoint_digest':result.checkpoint_digest,'model_version':result.model_version,'runtime_ms':result.runtime_ms,'predicted_area_m2':int(mask.sum()),**result.metadata}
  (folder/'metrics.json').write_text(json.dumps(metrics,indent=2)); summaries.append(metrics); print(json.dumps(metrics),flush=True)
(root/'benchmark-summary.json').write_text(json.dumps(summaries,indent=2))

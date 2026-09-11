"""Actual local HTTP transport fixtures. Synthetic results, never GPU acceptance."""
import json
import hashlib
from pathlib import Path
from uuid import uuid4
import numpy as np
from geoai.lan_compute import LanHttpComputeProvider
from geoai.worker_contract import ImagePayload,ModelWorkerRequest,ModelWorkerError,probability_metrics


def main():
    endpoint={'enabled':True,'base_url':'http://127.0.0.1:8001','timeout_seconds':20,'health_path':'/health','model_info_path':'/model-info','inference_path':'/v1/inference/oneshot-segmentation','usage_policy':'internal_only','model_name':'fake-real-rgb','model_version':'1','checkpoint_digest':hashlib.sha256(b'geoai-fake-real-rgb-v1').hexdigest()}
    provider=LanHttpComputeProvider(endpoint,allowed_hosts=('127.0.0.1',))
    try:
        assert provider.healthcheck()['model_info']['synthetic'] is True
        yy,xx=np.indices((512,512))
        support=np.stack([xx%256,yy%256,(xx+yy)%256]).astype('uint8')
        mask=np.zeros((1,512,512),dtype='uint8')
        mask[:,100:200,100:200]=1
        records=[]
        for name,query in [('support_equals_query',support),('same_color_different_query',np.roll(support,117,axis=2)),('unrelated_query',np.full_like(support,255))]:
            request=ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=uuid4(),support_image=ImagePayload.from_pixels(support),support_mask=ImagePayload.from_pixels(mask),query_image=ImagePayload.from_pixels(query),seed=57)
            response=provider.execute(request)
            repeated=provider.execute(request)
            assert response.probability_mask==repeated.probability_mask
            stats=probability_metrics(response.probabilities())
            if name!='unrelated_query':
                assert not stats['degenerate']
            record={'fixture':name,'synthetic':True,'real_model_acceptance':False,**stats,'runtime_ms':response.runtime_ms,'gpu_memory_peak':None,'seed':request.seed,'slot_id':None,'endpoint_id':None,'model_release_id':str(request.model_release_id),'checkpoint_digest':response.checkpoint_digest}
            records.append(record)
            provider.cancel(request.job_id,request.attempt_id)
            try:
                provider.execute(request)
            except ModelWorkerError as error:
                assert error.code=='cancelled'
            else:
                raise AssertionError('Cancelled attempt returned a result')
        path=Path(__file__).resolve().parents[1]/'artifacts/p9-http-fixtures.json'
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(records,indent=2)+'\n')
        print(json.dumps(records,indent=2))
        print('PASS: actual local HTTP, deterministic output and cancellation; NOT SkySense++ acceptance')
    finally:
        provider.close()


if __name__=='__main__':
    main()

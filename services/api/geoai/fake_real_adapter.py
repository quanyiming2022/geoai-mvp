"""CPU transport fixture; explicitly not a research model or real-model acceptance."""
import base64
import hashlib
import time
import numpy as np
from .worker_contract import ModelWorkerResponse, probability_metrics


class FakeRealAdapter:
    def healthcheck(self):
        return {'status':'ok','cuda':False,'model_loaded':True,'synthetic':True}

    def model_info(self):
        return {'model_name':'fake-real-rgb','model_version':'1','checkpoint_digest':hashlib.sha256(b'geoai-fake-real-rgb-v1').hexdigest(),'git_commit':None,'runtime_version':np.__version__,'cuda_version':None,'gpu_name':None,'gpu_memory_total':None,'usage_policy':'internal_only','synthetic':True}

    def infer(self,request):
        started=time.perf_counter()
        support=request.support_image.pixels().astype('float32')/255
        query=request.query_image.pixels().astype('float32')/255
        selected=request.support_mask.pixels()[0].astype(bool)
        color=support[:,selected].mean(axis=1)[:,None,None]
        distance=np.square(query-color).mean(axis=0)
        noise=np.random.default_rng(request.seed).uniform(-.005,.005,(512,512))
        probability=np.clip(np.exp(-distance*12)+noise,0,1).astype('<f4')
        info=self.model_info()
        return ModelWorkerResponse(job_id=request.job_id,attempt_id=request.attempt_id,model_release_id=request.model_release_id,probability_mask=base64.b64encode(probability.tobytes()).decode(),width=512,height=512,model_name=info['model_name'],model_version=info['model_version'],checkpoint_digest=info['checkpoint_digest'],runtime_ms=(time.perf_counter()-started)*1000,metadata={**probability_metrics(probability),'seed':request.seed,'synthetic':True,'usage_policy':'internal_only','gpu_memory_peak':None,'slot_id':None})

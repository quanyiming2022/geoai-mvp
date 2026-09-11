"""Remote-only SkySense++ bridge. Research-only; CUDA/checkpoint validation pending."""
import base64
import hashlib
from functools import partial
import os
from pathlib import Path
import random
import subprocess
import sys
from threading import Lock
import time
import numpy as np
from geoai.worker_contract import ModelWorkerResponse,ModelWorkerError,probability_metrics

UPSTREAM_COMMIT='cb0c6b774471ad3314354041c8fa6aae7d49a9bb'


def enable_memory_efficient_attention(model):
    """Skip unused attention weights only inside the audited MMCV wrapper.

    MMCV 1.7.1 MultiheadAttention consumes tuple element zero only. Asking
    PyTorch for weights materializes a 128 GiB matrix for the native tile.
    need_weights=False selects SDPA without changing parameters/state keys.
    Ordinary attention modules retain their original return contract.
    """
    import torch
    from mmcv.cnn.bricks.transformer import MultiheadAttention
    changed=0
    for wrapper in model.modules():
        if type(wrapper) is MultiheadAttention and type(wrapper.attn) is torch.nn.MultiheadAttention:
            attention=wrapper.attn
            if not getattr(attention,'_geoai_no_weights',False):
                attention.forward=partial(attention.forward,need_weights=False)
                attention._geoai_no_weights=True
                changed+=1
    return changed


def composite_inputs(support,mask,query):
    """Support on top, query on bottom; no query annotation/ground truth provided."""
    if support.shape!=(3,512,512) or query.shape!=(3,512,512) or mask.shape!=(1,512,512):
        raise ValueError('Expected fixed-size RGB and binary mask')
    if not set(np.unique(mask))<={0,1} or not mask.any():
        raise ValueError('Expected nonempty binary mask')
    mean=np.array([.485,.456,.406],dtype='float32')[:,None,None]
    std=np.array([.229,.224,.225],dtype='float32')[:,None,None]
    image=np.concatenate([support,query],axis=1).astype('float32')/255
    annotation=np.repeat(np.concatenate([mask,np.zeros_like(mask)],axis=1),3,axis=0).astype('float32')
    anno_mask=np.zeros((8,4),dtype='int64')
    anno_mask[4:]=1
    return (image-mean)/std,(annotation-mean)/std,anno_mask


class ResearchSkySensePPAdapter:
    usage_policy='research_only'

    def __init__(self):
        self.predictor=None
        self.torch=None
        self.checkpoint_digest=None
        self.version=os.environ.get('SKYSENSE_MODEL_VERSION','unconfigured')
        self.lock=Lock()
        self.load_error='model_not_loaded'
        try:
            self._load()
        except Exception:
            # Never expose local paths, license material, environment or stack traces to clients.
            self.predictor=None

    def _load(self):
        import torch
        self.torch=torch
        if not torch.cuda.is_available():
            return
        source=Path(os.environ['SKYSENSE_SOURCE']).resolve()
        checkpoint=Path(os.environ['SKYSENSE_CHECKPOINT']).resolve()
        expected=os.environ['SKYSENSE_CHECKPOINT_SHA256']
        commit=subprocess.run(['git','-C',str(source),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
        clean=subprocess.run(['git','-C',str(source),'diff','--quiet','HEAD','--'],check=False).returncode==0
        if commit!=UPSTREAM_COMMIT or not clean:
            raise ValueError('Pinned source required')
        with checkpoint.open('rb') as data:
            hasher=hashlib.sha256()
            for chunk in iter(lambda:data.read(1024*1024),b''):
                hasher.update(chunk)
            digest=hasher.hexdigest()
        if digest!=expected or self.version=='unconfigured':
            raise ValueError('Configured checkpoint identity required')
        sys.path.insert(0,str(source))
        from lib.predictors.flood3i_1shot import build_online_predictor
        predictor=build_online_predictor(str(checkpoint),str(source/'configs/eval_skysense_pp_flood3i.yml'))
        predictor.load(with_ckpt=True)
        predictor.model.eval()
        self.efficient_attention_modules=enable_memory_efficient_attention(predictor.model)
        self.predictor=predictor
        self.checkpoint_digest=digest

    def healthcheck(self):
        return {'status':'ok','cuda':bool(self.torch and self.torch.cuda.is_available()),'model_loaded':self.predictor is not None}

    def model_info(self):
        gpu=self.torch and self.torch.cuda.is_available()
        return {'model_name':'SkySense++','model_version':self.version,'checkpoint_digest':self.checkpoint_digest,'git_commit':UPSTREAM_COMMIT,'runtime_version':self.torch.__version__ if self.torch else None,'cuda_version':self.torch.version.cuda if self.torch else None,'gpu_name':self.torch.cuda.get_device_name(0) if gpu else None,'gpu_memory_total':self.torch.cuda.get_device_properties(0).total_memory if gpu else None,'usage_policy':'research_only'}

    def infer(self,request):
        if self.predictor is None:
            raise ModelWorkerError('model_not_loaded')
        with self.lock:
            torch=self.torch
            try:
                from antmmf.structures import Sample,SampleList
                random.seed(request.seed)
                np.random.seed(request.seed)
                torch.manual_seed(request.seed)
                torch.cuda.manual_seed_all(request.seed)
                torch.backends.cudnn.deterministic=True
                torch.backends.cudnn.benchmark=False
                torch.use_deterministic_algorithms(True)
                model=self.predictor.model
                core=model.module if hasattr(model,'module') else model
                # Upstream shuffles in-place: reset before seeding each invocation.
                core.vocabulary=list(range(1,core.vocabulary_size+1))
                image,annotation,anno_mask=composite_inputs(request.support_image.pixels(),request.support_mask.pixels(),request.query_image.pixels())
                sample=Sample()
                for key,value in {'img_name':str(request.job_id),'dataset_name':'flood3i','hr_img':torch.from_numpy(image),'targets':torch.from_numpy(annotation),'anno_mask':torch.from_numpy(anno_mask),'valid':torch.ones_like(torch.from_numpy(annotation)),'s2_img':torch.zeros(10,1,32,16),'s1_img':torch.zeros(2,1,32,16),'s2_ct':-1,'s2_ct2':-1,'location':None,'modality_idx':4,'modality_flag_hr':True,'modality_flag_s2':False,'modality_flag_s1':False,'task_type':'test'}.items():
                    sample[key]=value
                samples=SampleList([sample]).to(self.predictor.device)
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                started=time.perf_counter()
                with torch.inference_mode(),torch.autocast(device_type='cuda',dtype=torch.bfloat16):
                    output=model(samples)
                mapping=output['idx_2_color']
                slots=[int(slot) for slot,color in mapping.items() if int(color)>0]
                logits=output['logits_hr'].float()
                if len(slots)!=1 or tuple(logits.shape[-2:])!=(1024,512) or logits.shape[0]!=1:
                    raise ModelWorkerError('invalid_response')
                slot=slots[0]
                if not 0<slot<logits.shape[1]:
                    raise ModelWorkerError('invalid_response')
                probability=logits.softmax(dim=1)[0,slot,512:,:].cpu().numpy().astype('<f4')
                torch.cuda.synchronize()
                runtime_ms=(time.perf_counter()-started)*1000
                return ModelWorkerResponse(job_id=request.job_id,attempt_id=request.attempt_id,model_release_id=request.model_release_id,probability_mask=base64.b64encode(probability.tobytes()).decode(),width=512,height=512,model_name='SkySense++',model_version=self.version,checkpoint_digest=self.checkpoint_digest,runtime_ms=runtime_ms,metadata={**probability_metrics(probability),'seed':request.seed,'slot_id':slot,'gpu_memory_peak':torch.cuda.max_memory_allocated(),'usage_policy':'research_only','git_commit':UPSTREAM_COMMIT,'attention_backend':'pytorch_sdpa','efficient_attention_modules':self.efficient_attention_modules})
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                raise ModelWorkerError('cuda_oom') from None
            except ModelWorkerError:
                raise
            except Exception:
                raise ModelWorkerError('inference_failed') from None

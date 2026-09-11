"""Standalone local fake HTTP worker. No platform/database credentials required."""
from collections import OrderedDict
from threading import Lock,BoundedSemaphore
from uuid import UUID
from fastapi import FastAPI, HTTPException
from starlette.concurrency import run_in_threadpool
from .worker_contract import ModelWorkerRequest,ModelWorkerError,ModelAdapter
from .fake_real_adapter import FakeRealAdapter

app=FastAPI(title='GeoAI Worker Contract Fixture')
adapter:ModelAdapter=FakeRealAdapter()
lock=Lock()
slots=BoundedSemaphore(1)
cancelled=OrderedDict()


@app.get('/health')
def health():
    return adapter.healthcheck()


@app.get('/model-info')
def info():
    return adapter.model_info()


@app.delete('/v1/jobs/{job_id}/attempts/{attempt_id}')
def cancel(job_id:UUID,attempt_id:UUID):
    with lock:
        cancelled[(job_id,attempt_id)]=True
        while len(cancelled)>10000:
            cancelled.popitem(last=False)
    return {'status':'cancelled'}


@app.post('/v1/inference/oneshot-segmentation')
async def inference(request:ModelWorkerRequest):
    key=(request.job_id,request.attempt_id)
    with lock:
        if key in cancelled:
            raise HTTPException(409,{'code':'cancelled'})
    if not slots.acquire(blocking=False):
        raise HTTPException(503,{'code':'inference_failed'})
    try:
        result=await run_in_threadpool(adapter.infer,request)
    except ModelWorkerError as error:
        raise HTTPException(503 if error.code in ('cuda_oom','model_not_loaded') else 500,{'code':error.code}) from None
    finally:
        slots.release()
    with lock:
        if key in cancelled:
            raise HTTPException(409,{'code':'cancelled'})
    return result

"""Versioned, URL-free single-tile wire contract shared by platform and workers."""
import base64
import binascii
from typing import Literal, Protocol
from uuid import UUID
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from rasterio.io import MemoryFile


class ImagePayload(BaseModel):
    model_config=ConfigDict(extra='forbid')
    encoding: Literal['png_base64']='png_base64'
    data: str=Field(max_length=2_000_000)

    def pixels(self):
        try:
            blob=base64.b64decode(self.data,validate=True)
            if not blob.startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('PNG required')
            with MemoryFile(blob) as memory, memory.open() as ds:
                if ds.driver!='PNG' or ds.width!=512 or ds.height!=512 or ds.count not in (1,3) or any(t!='uint8' for t in ds.dtypes):
                    raise ValueError('Expected uint8 RGB or binary 512x512 PNG')
                return ds.read()
        except Exception as exc:
            raise ValueError('Invalid fixed-size PNG payload') from exc

    @model_validator(mode='after')
    def validate_png(self):
        self.pixels()
        return self

    @classmethod
    def from_pixels(cls,pixels):
        data=np.asarray(pixels)
        if data.ndim!=3 or data.shape[1:]!=(512,512) or data.shape[0] not in (1,3) or data.dtype!=np.uint8:
            raise ValueError('Expected 1 or 3 channel uint8 512x512 image')
        with MemoryFile() as memory:
            with memory.open(driver='PNG',width=512,height=512,count=data.shape[0],dtype='uint8') as ds:
                ds.write(data)
            return cls(data=base64.b64encode(memory.read()).decode())


class ModelWorkerRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_schema_version: Literal['1']='1'
    job_id: UUID
    attempt_id: UUID
    model_release_id: UUID
    support_image: ImagePayload
    support_mask: ImagePayload
    query_image: ImagePayload
    seed: int=Field(ge=0,le=4294967295,strict=True)

    @model_validator(mode='after')
    def validate_channels(self):
        if self.support_image.pixels().shape[0]!=3 or self.query_image.pixels().shape[0]!=3:
            raise ValueError('Support and query require RGB')
        mask=self.support_mask.pixels()
        if mask.shape[0]!=1 or not set(np.unique(mask))<={0,1} or not mask.any():
            raise ValueError('Support requires a nonempty binary 0/1 mask')
        return self


class ModelWorkerResponse(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    response_schema_version: Literal['1']='1'
    job_id: UUID
    attempt_id: UUID
    model_release_id: UUID
    probability_mask: str=Field(min_length=1398104,max_length=1398104)
    probability_encoding: Literal['float32_le_base64']='float32_le_base64'
    width: Literal[512]
    height: Literal[512]
    model_name: str=Field(min_length=1,max_length=120)
    model_version: str=Field(min_length=1,max_length=120)
    checkpoint_digest: str=Field(pattern=r'^[0-9a-f]{64}$')
    runtime_ms: float=Field(ge=0)
    metadata: dict[str,JsonValue]

    def probabilities(self):
        try:
            data=base64.b64decode(self.probability_mask,validate=True)
            if len(data)!=512*512*4:
                raise ValueError('Invalid probability size')
            values=np.frombuffer(data,dtype='<f4').reshape(512,512)
            if not np.isfinite(values).all() or values.min()<0 or values.max()>1:
                raise ValueError('Invalid probability values')
            return values
        except (binascii.Error,ValueError) as exc:
            raise ValueError('Invalid probability mask') from exc

    @model_validator(mode='after')
    def validate_probability(self):
        self.probabilities()
        return self


ErrorCode=Literal['endpoint_unreachable','healthcheck_failed','model_not_loaded','request_timeout','cuda_oom','inference_failed','invalid_response','cancelled']


class ModelWorkerError(RuntimeError):
    def __init__(self,code: ErrorCode,retryable=False):
        self.code,self.retryable=code,retryable
        super().__init__(code)


class ModelAdapter(Protocol):
    def healthcheck(self)->dict: ...
    def model_info(self)->dict: ...
    def infer(self,request: ModelWorkerRequest)->ModelWorkerResponse: ...


class ComputeProvider(Protocol):
    def healthcheck(self)->dict: ...
    def execute(self,request: ModelWorkerRequest)->ModelWorkerResponse: ...
    def cancel(self,job_id: UUID,attempt_id: UUID)->None: ...


def probability_metrics(values):
    mean,std=float(values.mean()),float(values.std())
    ratio=float((values>=.5).mean())
    return {'probability_mean':mean,'probability_std':std,'foreground_ratio':ratio,'mask_area':int((values>=.5).sum()),'degenerate':std<1e-6 or ratio<.001 or ratio>.999}

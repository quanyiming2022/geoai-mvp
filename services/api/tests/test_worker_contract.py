import base64
from uuid import uuid4
import numpy as np
import pytest
from pydantic import ValidationError
from geoai.worker_contract import ModelWorkerRequest, ModelWorkerResponse, ImagePayload


def test_payload_rejects_urls_and_wrong_dimensions():
    with pytest.raises(ValidationError):
        ImagePayload(encoding='png_base64',data='http://localhost/private')


def test_probability_requires_finite_exact_grid():
    data=np.full((512,512),.5,dtype='<f4')
    args=dict(job_id=uuid4(),attempt_id=uuid4(),model_release_id=uuid4(),probability_mask=base64.b64encode(data.tobytes()).decode(),width=512,height=512,model_name='fake-real',model_version='1',checkpoint_digest='a'*64,runtime_ms=1,metadata={})
    assert ModelWorkerResponse(**args).probabilities().shape==(512,512)
    data[0,0]=np.nan
    with pytest.raises(ValidationError):
        ModelWorkerResponse(**{**args,'probability_mask':base64.b64encode(data.tobytes()).decode()})
    with pytest.raises(ValidationError):
        ModelWorkerResponse(**{**args,'width':1024})


def test_request_forbids_arbitrary_model_urls():
    with pytest.raises(ValidationError):
        ModelWorkerRequest(job_id=uuid4(),model_url='http://localhost')

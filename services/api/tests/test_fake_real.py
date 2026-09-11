from uuid import uuid4
import numpy as np
from fastapi.testclient import TestClient
from geoai.worker_contract import ImagePayload,ModelWorkerRequest,ModelWorkerResponse
from geoai.model_worker import app


def request_fixture():
    yy,xx=np.indices((512,512))
    rgb=np.stack([xx%256,yy%256,(xx+yy)%256]).astype('uint8')
    mask=np.zeros((1,512,512),dtype='uint8')
    mask[:,100:200,100:200]=1
    return ModelWorkerRequest(job_id=uuid4(),attempt_id=uuid4(),model_release_id=uuid4(),seed=57,support_image=ImagePayload.from_pixels(rgb),support_mask=ImagePayload.from_pixels(mask),query_image=ImagePayload.from_pixels(rgb))


def test_http_contract_is_seeded_nonconstant_and_cancellable():
    client=TestClient(app)
    request=request_fixture()
    assert client.get('/health').json()['model_loaded']
    assert client.get('/model-info').json()['synthetic']
    first=ModelWorkerResponse.model_validate(client.post('/v1/inference/oneshot-segmentation',json=request.model_dump(mode='json')).raise_for_status().json())
    second=client.post('/v1/inference/oneshot-segmentation',json=request.model_dump(mode='json')).raise_for_status().json()
    assert first.probability_mask==second['probability_mask'] and first.probabilities().std()>.01
    client.delete(f'/v1/jobs/{request.job_id}/attempts/{request.attempt_id}').raise_for_status()
    assert client.post('/v1/inference/oneshot-segmentation',json=request.model_dump(mode='json')).status_code==409

import httpx
import pytest
from geoai.lan_compute import validate_origin,LanHttpComputeProvider
from geoai.worker_contract import ModelWorkerError


@pytest.mark.parametrize('url',['http://127.0.0.1','http://169.254.169.254','http://user:pass@192.168.1.50','http://192.168.1.50/private','http://example.com','file:///tmp/a','http://0.0.0.0'])
def test_endpoint_origins_reject_ssrf_targets(url):
    with pytest.raises(ValueError):
        validate_origin(url)


def test_lan_address_requires_no_hardcoded_host():
    assert validate_origin('http://10.20.30.40:8001/')=='http://10.20.30.40:8001'


def test_offline_classification():
    def fail(request):
        raise httpx.ConnectError('unreachable')
    endpoint={'enabled':True,'base_url':'http://10.20.30.40:8001','timeout_seconds':1,'health_path':'/health','model_info_path':'/model-info','usage_policy':'research_only'}
    provider=LanHttpComputeProvider(endpoint,transport=httpx.MockTransport(fail))
    with pytest.raises(ModelWorkerError) as error:
        provider.healthcheck()
    assert error.value.code=='endpoint_unreachable'
    provider.close()


def test_slow_dripping_response_obeys_total_deadline():
    import asyncio
    import time

    class Drip(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(.015)
                yield b' '

    endpoint={'enabled':True,'base_url':'http://10.20.30.40:8001','timeout_seconds':1,'health_path':'/health','model_info_path':'/model-info','usage_policy':'research_only'}
    provider=LanHttpComputeProvider(endpoint,transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Drip())))
    started=time.monotonic()
    with pytest.raises(ModelWorkerError) as error:
        provider.call('GET','/health',timeout=.08)
    assert error.value.code=='request_timeout'
    assert time.monotonic()-started<.5
    provider.close()


def test_failed_health_http_status_is_not_inference_failure():
    endpoint={'enabled':True,'base_url':'http://10.20.30.40:8001','timeout_seconds':1,'health_path':'/health','model_info_path':'/model-info','usage_policy':'research_only'}
    provider=LanHttpComputeProvider(endpoint,transport=httpx.MockTransport(lambda request:httpx.Response(503,json={'status':'bad'})))
    with pytest.raises(ModelWorkerError) as error:
        provider.healthcheck()
    assert error.value.code=='healthcheck_failed'


def test_disabled_endpoint_allows_diagnostics_but_never_inference():
    calls=[]
    endpoint={'enabled':False,'base_url':'http://10.20.30.40:8001','timeout_seconds':1,'health_path':'/health','model_info_path':'/model-info','usage_policy':'research_only'}
    def respond(request):
        calls.append((request.method,request.url.path))
        data={'status':'ok','cuda':True,'model_loaded':True} if request.url.path=='/health' else {'model_name':'SkySense++','model_version':'research-v1','checkpoint_digest':'a'*64,'usage_policy':'research_only'}
        return httpx.Response(200,json=data)
    with pytest.raises(ModelWorkerError):
        LanHttpComputeProvider(endpoint)
    provider=LanHttpComputeProvider(endpoint,transport=httpx.MockTransport(respond),healthcheck_only=True)
    assert provider.healthcheck()['model_info']['model_name']=='SkySense++'
    for method,path in [('POST','/v1/inference/oneshot-segmentation'),('DELETE','/v1/jobs/a/attempts/b'),('GET','/not-a-health-route')]:
        with pytest.raises(ModelWorkerError):
            provider.call(method,path)
    with pytest.raises(ModelWorkerError):
        provider.execute(None)
    assert endpoint['enabled'] is False
    assert calls==[('GET','/health'),('GET','/model-info')]

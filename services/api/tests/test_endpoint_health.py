import httpx
import pytest
from geoai import endpoints
from geoai.lan_compute import LanHttpComputeProvider


def test_registered_health_tracks_offline_and_recovery_without_enabling(monkeypatch):
    online = True
    endpoint = dict(enabled=False, base_url='http://10.20.30.40:8001', timeout_seconds=1,
                    health_path='/health', model_info_path='/model-info', provider_type='lan_http',
                    model_name='SkySense++', model_version='v1', checkpoint_digest='a'*64,
                    usage_policy='research_only')
    def respond(request):
        if not online:
            raise httpx.ConnectError('offline')
        return httpx.Response(200, json=dict(status='ok', cuda=True, model_loaded=True)
                              if request.url.path == '/health' else endpoint)
    monkeypatch.setattr(endpoints, 'LanHttpComputeProvider', lambda *a, **kw:
                        LanHttpComputeProvider(*a, **kw, transport=httpx.MockTransport(respond)))
    assert hasattr(endpoints, 'probe_endpoint'), 'Shared registered-endpoint health probe is missing'
    assert endpoints.probe_endpoint(endpoint)[0] == 'healthy'
    online = False
    assert endpoints.probe_endpoint(endpoint)[:2] == ('offline', 'endpoint_unreachable')
    online = True
    assert endpoints.probe_endpoint(endpoint)[0] == 'healthy'
    assert endpoint['enabled'] is False

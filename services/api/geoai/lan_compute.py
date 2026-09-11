"""Bounded HTTP transport for a server-registered endpoint; never accepts job URLs."""
import asyncio
import ipaddress
import json
import os
import re
import time
from urllib.parse import urlsplit
import httpx
from pydantic import ValidationError
from .worker_contract import ModelWorkerResponse, ModelWorkerError


def validate_origin(value,allowed_hosts=()):
    url=urlsplit(value)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):
        raise ValueError('Use an HTTP(S) server origin without credentials or paths')
    try:
        port=url.port
    except ValueError:
        raise ValueError('Invalid port') from None
    if port is not None and not 1<=port<=65535:
        raise ValueError('Invalid port')
    if url.hostname not in allowed_hosts:
        try:
            address=ipaddress.ip_address(url.hostname)
        except ValueError:
            raise ValueError('Use a literal LAN IP; hostnames require server allowlisting') from None
        networks=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','fc00::/7')
        if not any(address in ipaddress.ip_network(net) for net in networks):
            raise ValueError('Endpoint must use an allowed LAN address')
    return value.rstrip('/')


class LanHttpComputeProvider:
    def __init__(self,endpoint,transport=None,allowed_hosts=(),healthcheck_only=False):
        self.healthcheck_only=healthcheck_only
        if not endpoint['enabled'] and not healthcheck_only:
            raise ModelWorkerError('endpoint_unreachable')
        for field in ('health_path','model_info_path','inference_path'):
            if not re.fullmatch(r'/[A-Za-z0-9_-][A-Za-z0-9/_-]*',endpoint.get(field,'/health')):
                raise ValueError('Invalid worker path')
        self.endpoint=endpoint
        self.origin=validate_origin(endpoint['base_url'],allowed_hosts)
        headers={}
        if endpoint.get('auth_type','none')!='none':
            secret=os.environ.get(endpoint.get('secret_ref',''))
            if not secret:
                raise ModelWorkerError('healthcheck_failed')
            headers={'Authorization':'Bearer '+secret} if endpoint['auth_type']=='bearer' else {'X-API-Key':secret}
        self.headers,self.transport=headers,transport

    def close(self):
        pass  # Each call owns and closes its async client.

    def call(self,method,path,body=None,timeout=None):
        if self.healthcheck_only and (method!='GET' or path not in (self.endpoint['health_path'],self.endpoint['model_info_path'])):
            raise ModelWorkerError('endpoint_unreachable')
        return asyncio.run(self._call(method,path,body,timeout or self.endpoint['timeout_seconds']))

    async def _call(self,method,path,body,timeout):
        try:
            async with asyncio.timeout(timeout):
                async with httpx.AsyncClient(base_url=self.origin,headers=self.headers,timeout=timeout,follow_redirects=False,trust_env=False,transport=self.transport) as client, client.stream(method,path,json=body) as response:
                    content=bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content)>2_000_000:
                            raise ModelWorkerError('invalid_response')
                    if response.status_code>=300:
                        code=None
                        try:
                            payload=json.loads(content)
                            detail=payload.get('detail',payload)
                            code=detail.get('code') if isinstance(detail,dict) else None
                        except (ValueError,AttributeError):
                            pass
                        if code in ('cuda_oom','model_not_loaded','cancelled','inference_failed'):
                            raise ModelWorkerError(code)
                        raise ModelWorkerError('inference_failed',response.status_code in (502,503,504))
                    return json.loads(content)
        except (TimeoutError,httpx.TimeoutException):
            raise ModelWorkerError('request_timeout',True) from None
        except httpx.HTTPError:
            raise ModelWorkerError('endpoint_unreachable',True) from None
        except (ValueError,UnicodeError):
            raise ModelWorkerError('invalid_response') from None

    def healthcheck(self):
        try:
            health=self.call('GET',self.endpoint['health_path'],timeout=min(5,self.endpoint['timeout_seconds']))
        except ModelWorkerError as error:
            if error.code in ('inference_failed','invalid_response'):
                raise ModelWorkerError('healthcheck_failed') from None
            raise
        if not isinstance(health,dict) or health.get('status')!='ok':
            raise ModelWorkerError('healthcheck_failed')
        if health.get('model_loaded') is not True:
            raise ModelWorkerError('model_not_loaded')
        if self.endpoint['usage_policy']=='research_only' and health.get('cuda') is not True:
            raise ModelWorkerError('healthcheck_failed')
        info=self.call('GET',self.endpoint['model_info_path'],timeout=min(5,self.endpoint['timeout_seconds']))
        if not isinstance(info,dict) or not all(info.get(k) for k in ('model_name','model_version','checkpoint_digest','usage_policy')):
            raise ModelWorkerError('invalid_response')
        if self.endpoint['usage_policy']!=info['usage_policy']:
            raise ModelWorkerError('invalid_response')
        return {'health':health,'model_info':info}

    def execute(self,request):
        if self.healthcheck_only or not self.endpoint['enabled']:
            raise ModelWorkerError('endpoint_unreachable')
        deadline=time.monotonic()+self.endpoint['timeout_seconds']
        for attempt in range(2):
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise ModelWorkerError('request_timeout')
            try:
                payload=self.call('POST',self.endpoint['inference_path'],request.model_dump(mode='json'),remaining)
                response=ModelWorkerResponse.model_validate(payload)
                if (response.job_id,response.attempt_id,response.model_release_id)!=(request.job_id,request.attempt_id,request.model_release_id):
                    raise ModelWorkerError('invalid_response')
                expected=self.endpoint.get('checkpoint_digest')
                if not expected or response.checkpoint_digest!=expected:
                    raise ModelWorkerError('invalid_response')
                if any(response.model_dump()[key]!=self.endpoint.get(key) for key in ('model_name','model_version')) or response.metadata.get('usage_policy')!=self.endpoint['usage_policy']:
                    raise ModelWorkerError('invalid_response')
                return response
            except ValidationError:
                raise ModelWorkerError('invalid_response') from None
            except ModelWorkerError as error:
                if attempt or not error.retryable:
                    raise
        raise ModelWorkerError('inference_failed')

    def cancel(self,job_id,attempt_id):
        self.call('DELETE',f'/v1/jobs/{job_id}/attempts/{attempt_id}',timeout=5)

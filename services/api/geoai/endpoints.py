"""Administrator-managed model releases and registered compute servers."""
import os
from typing import Literal
from uuid import UUID
from datetime import datetime,timezone
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from psycopg.types.json import Jsonb
from .auth import CurrentUser
from .spatial import UserSQLRepository
from .lan_compute import validate_origin,LanHttpComputeProvider
from .worker_contract import ModelWorkerError


def allowed_hosts():
    return tuple(h.strip() for h in os.environ.get('MODEL_ENDPOINT_ALLOWED_HOSTS','').split(',') if h.strip())


class ReleaseInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=120)
    model_name:str=Field(min_length=1,max_length=120)
    model_version:str=Field(min_length=1,max_length=120)
    checkpoint_digest:str|None=Field(default=None,pattern=r'^[0-9a-f]{64}$')
    usage_policy:Literal['internal_only','research_only','commercial']='research_only'

    @model_validator(mode='after')
    def research_policy(self):
        if 'skysense' in self.model_name.lower() and self.usage_policy!='research_only':
            raise ValueError('SkySense++ must remain research_only')
        return self


class EndpointInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=120)
    provider_type:Literal['lan_http','runpod','local_gpu','mock']='lan_http'
    base_url:str=Field(max_length=250)
    health_path:str=Field(default='/health',pattern=r'^/[A-Za-z0-9_-][A-Za-z0-9/_-]*$',max_length=120)
    model_info_path:str=Field(default='/model-info',pattern=r'^/[A-Za-z0-9_-][A-Za-z0-9/_-]*$',max_length=120)
    inference_path:str=Field(default='/v1/inference/oneshot-segmentation',pattern=r'^/[A-Za-z0-9_-][A-Za-z0-9/_-]*$',max_length=120)
    request_schema_version:Literal['1']='1'
    timeout_seconds:int=Field(default=120,ge=1,le=300)
    model_release_id:UUID
    enabled:bool=False
    auth_type:Literal['none','bearer','api_key']='none'
    secret_ref:str|None=Field(default=None,pattern=r'^MODEL_ENDPOINT_[A-Z0-9_]+$')

    @model_validator(mode='after')
    def validate_configuration(self):
        self.base_url=validate_origin(self.base_url,allowed_hosts())
        if (self.auth_type=='none')!=(self.secret_ref is None):
            raise ValueError('Credentials must use a server-side secret reference')
        return self


class EndpointRepository(UserSQLRepository):
    def is_admin(self):
        return self.execute('SELECT geoai_internal.is_platform_admin() AS allowed')[0]['allowed']

    def require_admin(self):
        if not self.is_admin():
            raise HTTPException(403,'Platform administrator required')

    def releases(self):
        return self.execute('SELECT * FROM geoai_internal.model_releases ORDER BY name')

    def endpoints(self):
        self.require_admin()
        return self.execute('SELECT e.*,r.name AS release_name FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id ORDER BY e.created_at DESC')

    def endpoint(self,endpoint_id):
        self.require_admin()
        rows=self.execute('SELECT e.*,r.checkpoint_digest,r.model_name,r.model_version FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id WHERE e.id=%s',(endpoint_id,))
        if not rows:
            raise HTTPException(404,'Compute server not found')
        return rows[0]

    def save_release(self,data,release_id=None):
        self.require_admin()
        values=data.model_dump()
        fields=list(values)
        if release_id:
            query='UPDATE geoai_internal.model_releases SET '+','.join(f'{f}=%s' for f in fields)+' WHERE id=%s RETURNING *'
            params=(*values.values(),release_id)
        else:
            query='INSERT INTO geoai_internal.model_releases('+','.join(fields)+') VALUES ('+','.join(['%s']*len(fields))+') RETURNING *'
            params=tuple(values.values())
        rows=self.execute(query,params)
        if not rows:
            raise HTTPException(404,'Model release not found')
        return rows[0]

    def save(self,data,endpoint_id=None):
        self.require_admin()
        release=self.execute('SELECT usage_policy FROM geoai_internal.model_releases WHERE id=%s',(data.model_release_id,))
        if not release:
            raise HTTPException(422,'Choose a registered model release')
        values={**data.model_dump(),'usage_policy':release[0]['usage_policy']}
        fields=list(values)
        if endpoint_id:
            query='UPDATE geoai_internal.model_endpoints SET '+','.join(f'{f}=%s' for f in fields)+",updated_at=now(),health_status='offline',health_code=NULL,model_info=NULL WHERE id=%s RETURNING *"
            params=(*values.values(),endpoint_id)
        else:
            query='INSERT INTO geoai_internal.model_endpoints('+','.join(fields)+') VALUES ('+','.join(['%s']*len(fields))+') RETURNING *'
            params=tuple(values.values())
        rows=self.execute(query,params)
        if not rows:
            raise HTTPException(404,'Compute server not found')
        return rows[0]


router=APIRouter(tags=['model-endpoints'])


@router.get('/admin/access')
def admin_access(current:CurrentUser):
    return {'is_admin':EndpointRepository(current.user['id']).is_admin()}


@router.get('/admin/models')
def releases(current:CurrentUser):
    repo=EndpointRepository(current.user['id'])
    repo.require_admin()
    return repo.releases()


@router.post('/admin/models',status_code=201)
def create_release(data:ReleaseInput,current:CurrentUser):
    return EndpointRepository(current.user['id']).save_release(data)


@router.put('/admin/models/{release_id}')
def edit_release(release_id:UUID,data:ReleaseInput,current:CurrentUser):
    return EndpointRepository(current.user['id']).save_release(data,release_id)


@router.get('/admin/model-endpoints')
def list_endpoints(current:CurrentUser):
    return EndpointRepository(current.user['id']).endpoints()


@router.post('/admin/model-endpoints',status_code=201)
def create_endpoint(data:EndpointInput,current:CurrentUser):
    return EndpointRepository(current.user['id']).save(data)


@router.put('/admin/model-endpoints/{endpoint_id}')
def edit_endpoint(endpoint_id:UUID,data:EndpointInput,current:CurrentUser):
    return EndpointRepository(current.user['id']).save(data,endpoint_id)


@router.delete('/admin/model-endpoints/{endpoint_id}')
def delete_endpoint(endpoint_id:UUID,current:CurrentUser):
    repo=EndpointRepository(current.user['id'])
    repo.require_admin()
    rows=repo.execute('DELETE FROM geoai_internal.model_endpoints WHERE id=%s RETURNING id',(endpoint_id,))
    if not rows:
        raise HTTPException(404,'Compute server not found')
    return {'deleted':str(endpoint_id)}


@router.post('/admin/model-endpoints/{endpoint_id}/test')
def test_endpoint(endpoint_id:UUID,current:CurrentUser):
    repo=EndpointRepository(current.user['id'])
    endpoint=repo.endpoint(endpoint_id)
    status,code,info=probe_endpoint(endpoint)
    now=datetime.now(timezone.utc)
    saved=repo.execute("UPDATE geoai_internal.model_endpoints SET health_status=%s,health_code=%s,model_info=%s,last_checked_at=%s,last_healthy_at=CASE WHEN %s='healthy' THEN %s ELSE last_healthy_at END WHERE id=%s AND config_revision=%s RETURNING id",(status,code,Jsonb(info),now,status,now,endpoint_id,endpoint['config_revision']))
    if not saved:
        raise HTTPException(409,'Configuration changed during test; test the current configuration again')
    return {'status':status,'code':code,'model_info':info,'checked_at':now}


def probe_endpoint(endpoint):
    """Read-only diagnostics shared by admin tests and the internal monitor."""
    status,code,info='healthy',None,{}
    provider=None
    try:
        if endpoint['provider_type']!='lan_http':
            raise ModelWorkerError('healthcheck_failed')
        provider=LanHttpComputeProvider(endpoint,allowed_hosts=allowed_hosts(),healthcheck_only=True)
        response=provider.healthcheck()
        raw=response['model_info']
        info={k:raw.get(k) for k in ('model_name','model_version','checkpoint_digest','git_commit','runtime_version','cuda_version','gpu_name','gpu_memory_total','usage_policy','synthetic')}
        info.update(cuda=response['health'].get('cuda'),model_loaded=response['health'].get('model_loaded'))
        if any(endpoint.get(k)!=raw.get(k) for k in ('model_name','model_version','checkpoint_digest')):
            status,code='degraded','invalid_response'
    except ModelWorkerError as error:
        code=error.code
        status='offline' if code in ('endpoint_unreachable','request_timeout') else 'degraded'
    except ValueError:
        status,code='degraded','healthcheck_failed'
    finally:
        if provider:
            provider.close()
    return status,code,info

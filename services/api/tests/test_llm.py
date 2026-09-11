from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from geoai.llm import Intent,Profile,Configuration,initial,build_job,validate_remote


def resources():
    return {'rasters':[{'id':'r','filename':'image','status':'ready','width':1024,'height':1024,'bands':3}], 'prompts':[{'id':'p','name':'target','raster_asset_id':'r'}], 'aois':[{'id':'a','name':'area'}], 'endpoints':[]}

def test_profiles_preserve_all_modes_and_local_defaults():
    c=initial().checked()
    assert c.active_mode=='local' and len(c.profiles)==3 and c.profiles[0].enabled
    with pytest.raises(HTTPException):Configuration(profiles=[Profile(mode='local')]*3).checked()

def test_llm_cannot_inject_commands_or_arbitrary_urls():
    with pytest.raises(ValidationError):Intent(intent='extract',model_url='http://localhost',command='delete')
    with pytest.raises(ValidationError):Intent(intent='extract',query_col=2.1)
    with pytest.raises(ValidationError):Intent(intent='delete')

def test_origin_requires_server_allowlist(monkeypatch):
    monkeypatch.setenv('LLM_ALLOWED_ORIGINS','https://llm.example/v1')
    assert validate_remote(Profile(mode='cloud',base_url='https://llm.example/v1'))=='https://llm.example/v1'
    for url in ['http://169.254.169.254','http://127.0.0.1:8080','https://user:pass@llm.example/v1','https://llm.example/v1?x=1']:
        with pytest.raises(HTTPException):validate_remote(Profile(mode='cloud',base_url=url))

def test_model_resource_hallucination_is_rejected():
    with pytest.raises(HTTPException):build_job(Intent(intent='extract',channel='mock',raster_id='alien',prompt_id='p',aoi_id='a'),resources(),uuid4())

def test_worker_without_healthy_endpoint_does_not_fallback_to_mock():
    with pytest.raises(HTTPException):build_job(Intent(intent='extract',channel='worker',raster_id='r',prompt_id='p'),resources(),uuid4())

def test_worker_native_bounds_and_idempotency():
    r,p,e,m=map(str,[uuid4(),uuid4(),uuid4(),uuid4()]);data=resources();data['rasters'][0]['id']=r;data['prompts'][0].update(id=p,raster_asset_id=r);data['endpoints']=[{'id':e,'model_release_id':m,'config_revision':2,'health_status':'healthy','name':'GPU','model_name':'Research','usage_policy':'research_only'}]
    intent=Intent(intent='extract',channel='worker',raster_id=r,prompt_id=p,endpoint_id=e,query_col=100,query_row=200)
    token=uuid4();job,labels=build_job(intent,data,token)
    assert job.idempotency_key==token and job.query_col==100 and job.kind=='geoextract_tile' and job.seed==57
    intent.query_col=700
    with pytest.raises(HTTPException):build_job(intent,data,token)


def test_total_deadline_cancels_slow_provider(monkeypatch):
    import asyncio
    from geoai.llm import HttpLLMProvider
    cancelled=[]
    async def slow(self,messages,schema):
        try:await asyncio.sleep(10)
        finally:cancelled.append(True)
    monkeypatch.setattr(HttpLLMProvider,'_generate',slow)
    p=Profile(mode='local').model_copy(update={'timeout_seconds':.01})
    with pytest.raises(HTTPException) as error:HttpLLMProvider(p).generate([],{})
    assert error.value.status_code==504 and cancelled==[True]


def test_remote_cannot_be_activated_without_valid_address():
    config=initial();config.active_mode='lan'
    with pytest.raises(HTTPException):config.checked()


def test_decoding_schema_constrains_ids_to_visible_catalog():
    from geoai.llm import planner_schema
    schema=planner_schema(resources())
    assert schema['properties']['raster_id']=={'enum':[None,'r']}
    assert schema['properties']['endpoint_id']=={'enum':[None]}
    assert schema['additionalProperties'] is False
    assert set(schema['required'])==set(schema['properties'])

from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from geoai.agent_goals import AgentGoal,ResolutionError,resolve_resource,select_endpoint,enforce_goal_scope,capability_check,job_message
from geoai import workspace_agent as agent


def test_current_context_and_unique_names_resolve_without_guessing():
    items=[{'id':'a','name':'12aoi'},{'id':'b','name':'other'}]
    assert resolve_resource(items,None,'a','aoi_id')['id']=='a'
    assert resolve_resource(items,'other','a','aoi_id')['id']=='b'
    assert resolve_resource(items[:1],None,None,'aoi_id')['id']=='a'
    with pytest.raises(ResolutionError):resolve_resource(items,None,None,'aoi_id')
    with pytest.raises(ResolutionError):resolve_resource(items,'nonexistent','a','aoi_id')
    duplicates=[{'id':'a','name':'area'},{'id':'b','name':'area'}]
    with pytest.raises(ResolutionError):resolve_resource(duplicates,'area',None,'aoi_id')
    assert resolve_resource(duplicates,'area','b','aoi_id')['id']=='b'


def test_endpoints_auto_resolve_only_healthy_real_resources():
    real={'id':'e','name':'GPU','usage_policy':'research_only','health_status':'healthy'}
    fake={**real,'id':'f','usage_policy':'internal_only'}
    assert select_endpoint([real,fake])==real
    with pytest.raises(ResolutionError):select_endpoint([{**real,'health_status':'offline'}])
    with pytest.raises(ResolutionError):select_endpoint([real],'foreign')
    with pytest.raises(ResolutionError):select_endpoint([real,{**real,'id':'e2'}])

@pytest.mark.parametrize('text',['用这个样例提取当前范围','提取12aoi里所有建筑','扫描整个AOI'])
def test_full_area_goal_never_downgrades(text):
    goal=enforce_goal_scope(AgentGoal(goal_type='extract_similar'),text)
    assert goal.requested_execution_scope=='full_aoi' and not capability_check(goal)

def test_single_tile_followups_and_safe_error_interpretation():
    goal=enforce_goal_scope(AgentGoal(goal_type='extract_similar'),'用这个样例测试这里')
    assert goal.requested_execution_scope=='single_tile' and capability_check(goal)
    assert '显存不足' in job_message({'status':'failed','error_code':'cuda_oom'})
    assert '已完成' in job_message({'status':'succeeded','result':{'runtime_ms':8200,'result_count':3}})
    assert '8.20' in job_message({'status':'succeeded','result':{'runtime_ms':8200}})

@pytest.fixture
def env(monkeypatch):
    ids={k:str(uuid4()) for k in ('project','raster','prompt','aoi','endpoint','release','user')}
    resources={'rasters':[{'id':ids['raster'],'filename':'SPOT','status':'ready','width':1024,'height':1024,'bands':3}], 'prompts':[{'id':ids['prompt'],'name':'建筑-基准01','raster_asset_id':ids['raster']}], 'aois':[{'id':ids['aoi'],'name':'12aoi'}], 'endpoints':[{'id':ids['endpoint'],'name':'Lab','model_name':'SkySense++','model_release_id':ids['release'],'config_revision':1,'health_status':'healthy','usage_policy':'research_only'}]}
    details={'my_role':'owner'};recent={'id':str(uuid4()),'status':'succeeded','result':{'runtime_ms':8200,'result_count':2},'progress':100};result={'id':str(uuid4()),'job_id':recent['id'],'geometry':{'type':'Polygon','coordinates':[]}}
    monkeypatch.setattr(agent,'workspace',lambda *args:(details,resources,recent,result,{}))
    monkeypatch.setattr(agent.llm,'configuration',lambda:SimpleNamespace(active_mode='local'))
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:{'available':False,'execution_mode':'multi_tile_full_aoi','reason':'multi_tile_required'})
    saved={}
    class Cache:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def set(self,key,value,ex):saved[key]=value
        def get(self,key):return saved.get(key)
    monkeypatch.setattr(agent.llm,'cache',Cache)
    return ids,resources,details,recent,result,saved

def run(monkeypatch,env,goal,text='用这个样例测试这里',**fields):
    ids=env[0];monkeypatch.setattr(agent,'parse_goal',lambda *args:goal)
    context=agent.ViewContext(channel='worker',**fields)
    return agent.agent(ids['project'],agent.AgentRequest(text=text,workspace_context=context),SimpleNamespace(user={'id':ids['user']}))

def test_full_aoi_resolves_context_and_cannot_create_draft(monkeypatch,env):
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'))
    assert answer['code']=='CAPABILITY_NOT_AVAILABLE' and not any('llm:draft:' in key for key in env[-1])
    assert answer['labels']['视觉样例']=='建筑-基准01'

def test_ambiguous_aoi_requires_question_before_capability_rejection(monkeypatch,env):
    env[1]['aois'].append({'id':str(uuid4()),'name':'second'})
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'))
    assert answer['kind']=='clarification' and answer['field']=='aoi_id'
    assert len(answer['choices'])==2 and not any('llm:draft:' in key for key in env[-1])

def test_missing_map_position_and_offline_prevent_submission(monkeypatch,env):
    goal=AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile')
    assert run(monkeypatch,env,goal)['kind']=='select_window'
    env[1]['endpoints'][0]['health_status']='offline'
    answer=run(monkeypatch,env,goal)
    assert answer['kind']=='clarification' and '不可用' in answer['message'] and not any('llm:draft:' in key for key in env[-1])

def test_viewer_cannot_prepare_inference_and_owner_needs_confirmation(monkeypatch,env):
    goal=AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile')
    env[2]['my_role']='viewer'
    assert run(monkeypatch,env,goal)['kind']=='explanation' and not any('llm:draft:' in key for key in env[-1])
    env[2]['my_role']='owner'
    answer=run(monkeypatch,env,goal,raster_id=env[0]['raster'],query_col=0,query_row=0)
    assert answer['kind']=='draft' and len(env[-1])==1
    assert '研究模型' in answer['labels']['模型']

def test_recent_job_result_and_guarded_project_switch(monkeypatch,env):
    assert '8.20' in run(monkeypatch,env,AgentGoal(goal_type='check_job_status'))['message']
    result=run(monkeypatch,env,AgentGoal(goal_type='inspect_result'))
    assert result['ui_tool']['id']==env[4]['id']
    switch=run(monkeypatch,env,AgentGoal(goal_type='switch_project'))
    assert switch['ui_tool']=={'action':'switch_project'}

def test_goal_schema_has_no_executable_escape_hatch():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):AgentGoal(goal_type='test_model_here',url='http://localhost',sql='delete')


def test_llm_cannot_choose_unmentioned_resource_name(monkeypatch,env):
    env[1]['aois'].append({'id':str(uuid4()),'name':'other AOI'})
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi',aoi_name='other AOI'),text='提取这个项目里的建筑')
    assert answer['kind']=='clarification' and answer['field']=='aoi_id'
    assert not any('llm:draft:' in key for key in env[-1])

def test_whole_area_overrides_explicit_test_phrase(monkeypatch,env):
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),text='测试这里并扫描整个AOI')
    assert answer['code']=='CAPABILITY_NOT_AVAILABLE' and not any('llm:draft:' in key for key in env[-1])


def test_pending_clarification_continues_original_goal_without_llm(monkeypatch,env):
    other={'id':str(uuid4()),'name':'other'};env[1]['aois'].append(other)
    first=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取当前范围')
    monkeypatch.setattr(agent,'parse_goal',lambda *args:pytest.fail('must not reparse continuation'))
    request=agent.AgentRequest(text='other',continuation_id=first['continuation_id'],workspace_context=agent.ViewContext(channel='worker',aoi_id=other['id']))
    answer=agent.agent(env[0]['project'],request,SimpleNamespace(user={'id':env[0]['user']}))
    assert answer['code']=='CAPABILITY_NOT_AVAILABLE' and answer['labels']['范围']=='other'
    assert answer['conversation_state']=='BLOCKED'
    with pytest.raises(HTTPException) as e:agent.agent(env[0]['project'],request,SimpleNamespace(user={'id':str(uuid4())}))
    assert e.value.status_code==404

def test_map_continuation_freezes_resources_and_requires_explicit_scope_change(monkeypatch,env):
    first=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取整个AOI')
    context=agent.ViewContext(channel='worker',raster_id=str(uuid4()),query_col=0,query_row=0)
    request=agent.AgentRequest(text='开始',continuation_id=first['continuation_id'],workspace_context=context)
    blocked=agent.agent(env[0]['project'],request,SimpleNamespace(user={'id':env[0]['user']}))
    assert blocked['code']=='CAPABILITY_NOT_AVAILABLE'
    request=request.model_copy(update={'accept_single_tile':True})
    answer=agent.agent(env[0]['project'],request,SimpleNamespace(user={'id':env[0]['user']}))
    assert answer['kind']=='draft' and answer['context_update']['raster_id']==env[0]['raster']


def test_confirmed_cancel_delegates_to_existing_authorized_job_api(monkeypatch,env):
    env[3]['status']='running'
    first=run(monkeypatch,env,AgentGoal(goal_type='cancel_job'),text='取消刚才任务')
    assert first['kind']=='cancel_confirmation'
    calls=[]
    monkeypatch.setattr(agent,'control_job',lambda job,action,current:calls.append((str(job),action,current.user['id'])) or {'status':'cancelled'})
    request=agent.CancelConfirm(confirmation_id=first['confirmation_id'],confirmed=True)
    user=SimpleNamespace(user={'id':env[0]['user']})
    assert agent.cancel(env[0]['project'],request,user)['status']=='cancelled'
    assert calls==[(env[3]['id'],'cancel',env[0]['user'])]
    with pytest.raises(HTTPException) as e:agent.cancel(env[0]['project'],request,SimpleNamespace(user={'id':str(uuid4())}))
    assert e.value.status_code==404 and len(calls)==1


def test_small_full_aoi_auto_window_requires_confirmation_not_map(monkeypatch,env):
    ids=env[0]
    coverage={'available':True,'execution_mode':'single_tile_full_aoi','aoi_id':ids['aoi'],'raster_id':ids['raster'],'query_col':20,'query_row':30,'aoi_revision':1,'geometry':{'type':'Polygon','coordinates':[]}}
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:coverage)
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取整个AOI')
    assert answer['kind']=='draft' and answer['conversation_state']=='NEED_CONFIRMATION'
    assert answer['execution_mode']=='single_tile_full_aoi' and answer['query_window']==coverage
    assert 'select_window' not in answer.get('suggested_actions',[])
    import json
    draft=json.loads(env[-1]['geoai:llm:draft:'+answer['draft_id']])
    assert draft['execution_scope']=='full_aoi' and draft['job']['query_col']==20 and draft['job']['aoi_id']==ids['aoi']
    # Explicit local test does not inherit the automatic full-range position.
    assert run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'))['kind']=='select_window'


def test_auto_full_aoi_window_is_not_an_explicit_test_location(monkeypatch,env):
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),raster_id=env[0]['raster'],query_col=0,query_row=0,window_source='automatic')
    assert answer['kind']=='select_window'


def test_full_aoi_confirmation_rechecks_revision(monkeypatch,env):
    ids=env[0];coverage={'available':True,'execution_mode':'single_tile_full_aoi','aoi_id':ids['aoi'],'raster_id':ids['raster'],'query_col':20,'query_row':30,'aoi_revision':1}
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:coverage)
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取整个AOI')
    monkeypatch.setattr(agent.llm,'project',lambda *args:{'my_role':'owner'})
    calls=[];monkeypatch.setattr(agent.llm,'create_job',lambda *args:calls.append(args) or {'id':'submitted'})
    request=agent.llm.ConfirmInput(draft_id=answer['draft_id'],confirmed=True);user=SimpleNamespace(user={'id':ids['user']})
    coverage['aoi_revision']=2
    with pytest.raises(HTTPException) as error:agent.llm.confirm(ids['project'],request,user)
    assert error.value.status_code==409 and not calls
    coverage['aoi_revision']=1
    assert agent.llm.confirm(ids['project'],request,user)['id']=='submitted' and len(calls)==1

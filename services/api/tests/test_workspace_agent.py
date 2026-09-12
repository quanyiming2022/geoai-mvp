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

def valid_coverage(monkeypatch,env):
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda p,u,r,a:{'available':True,'execution_mode':'single_tile_full_aoi','aoi_id':str(a),'raster_id':str(r),'query_col':20,'query_row':30,'aoi_revision':1})


def test_automatic_aoi_and_offline_prevent_submission(monkeypatch,env):
    valid_coverage(monkeypatch,env)
    goal=AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile')
    assert run(monkeypatch,env,goal)['kind']=='draft'
    env[1]['endpoints'][0]['health_status']='offline'
    answer=run(monkeypatch,env,goal)
    assert answer['kind']=='clarification' and '不可用' in answer['message']

def test_viewer_cannot_prepare_inference_and_owner_needs_confirmation(monkeypatch,env):
    valid_coverage(monkeypatch,env)
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
    assert answer['kind']=='capability_unavailable' and answer['context_update']['raster_id']==env[0]['raster']


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
    # Test phrasing also uses automatic AOI coverage, never map selection.
    assert run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'))['kind']=='draft'


def test_auto_full_aoi_window_is_not_an_explicit_test_location(monkeypatch,env):
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),raster_id=env[0]['raster'],query_col=0,query_row=0,window_source='automatic')
    assert answer['kind']=='capability_unavailable'


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


def test_missing_aoi_offers_creation_and_pending_goal(monkeypatch,env):
    env[1]['aois']=[]
    response=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取整个范围')
    assert response['kind']=='clarification'
    assert response['suggested_actions']==['create_aoi']
    assert response['continuation_id']
    assert response['context_update']['prompt_id']==env[0]['prompt']
    ids=env[0]
    new_aoi={'id':ids['aoi'],'name':'新范围','geometry':{'type':'Polygon','coordinates':[]}}
    env[1]['aois'].append(new_aoi)
    coverage={'available':True,'execution_mode':'single_tile_full_aoi','aoi_id':ids['aoi'],'raster_id':ids['raster'],'query_col':0,'query_row':0,'aoi_revision':1}
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:coverage)
    monkeypatch.setattr(agent,'parse_goal',lambda *args: (_ for _ in ()).throw(AssertionError('must resume saved goal')))
    ctx={**response['context_update'],'aoi_id':ids['aoi']}
    resumed=agent.agent(ids['project'],agent.AgentRequest(text='已创建新范围',workspace_context=ctx,continuation_id=response['continuation_id']),SimpleNamespace(user={'id':ids['user']}))
    assert resumed['kind']=='draft' and resumed['execution_mode']=='single_tile_full_aoi'
    assert resumed['context_update']['prompt_id']==ids['prompt']


def test_worker_draft_accepts_prompt_from_another_raster(monkeypatch,env):
    valid_coverage(monkeypatch,env)
    other=str(uuid4())
    env[1]['rasters'].append({**env[1]['rasters'][0],'id':other,'filename':'Query B'})
    response=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),raster_id=other,prompt_id=env[0]['prompt'],query_col=0,query_row=0,window_source='map')
    assert response['kind']=='draft'
    assert response['labels']['影像']=='Query B'
    assert response['context_update']['prompt_id']==env[0]['prompt']


def test_outside_aoi_repairs_resource_without_offering_dead_map_action(monkeypatch,env):
    ids=env[0]
    other={'id':str(uuid4()),'name':'目标影像范围'}
    env[1]['aois'].append(other)
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda p,u,r,a: {'available':False,'execution_mode':'unavailable','reason':'outside_raster'} if str(a)==ids['aoi'] else {'available':True,'execution_mode':'single_tile_full_aoi','query_col':0,'query_row':0,'aoi_revision':1,'aoi_id':str(a),'raster_id':str(r)})
    first=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi',aoi_name='12aoi'),text='提取12aoi中的所有建筑',aoi_id=ids['aoi'])
    assert first['kind']=='clarification'
    assert first['field']=='aoi_id'
    assert first['choices']==[other]
    assert first['suggested_actions']==['create_aoi']
    assert not any('llm:draft:' in key for key in env[-1])
    ctx={**first['context_update'],'aoi_id':other['id']}
    resumed=agent.agent(ids['project'],agent.AgentRequest(text=other['name'],continuation_id=first['continuation_id'],workspace_context=ctx),SimpleNamespace(user={'id':ids['user']}))
    assert resumed['kind']=='draft'
    assert resumed['execution_mode']=='single_tile_full_aoi'
    assert resumed['context_update']['prompt_id']==ids['prompt']


def test_too_small_raster_does_not_offer_impossible_map_pick(monkeypatch,env):
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:{'available':False,'execution_mode':'unavailable','reason':'source_too_small'})
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'))
    assert answer['kind']=='clarification' and answer['field']=='raster_id'
    assert 'select_window' not in answer.get('suggested_actions',[])


def test_disjoint_aoi_local_test_requires_repair_before_map(monkeypatch,env):
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:{'available':False,'execution_mode':'single_tile_full_aoi','reason':'outside_raster','overlaps_raster':False})
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),aoi_id=env[0]['aoi'])
    assert answer['kind']=='clarification' and answer['field']=='aoi_id'
    assert answer['suggested_actions']==['create_aoi']
    assert not any('llm:draft:' in key for key in env[-1])


def test_selected_small_aoi_auto_covers_even_when_user_says_test(monkeypatch,env):
    ids=env[0]
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',lambda *args:{'available':True,'execution_mode':'single_tile_full_aoi','aoi_id':ids['aoi'],'raster_id':ids['raster'],'query_col':10,'query_row':20,'aoi_revision':1})
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),aoi_id=ids['aoi'])
    assert answer['kind']=='draft' and answer['execution_mode']=='single_tile_full_aoi'
    assert 'select_window' not in answer.get('suggested_actions',[])


@pytest.mark.parametrize('field,action',[('aoi_id','create_aoi'),('prompt_id','create_prompt'),('raster_id','add_raster')])
def test_ambiguous_resources_offer_creation_with_distinguishing_metadata(field,action):
    candidates=[{'id':'1','name':'同名','created_at':'2026-09-12T01:00:00Z'},{'id':'2','name':'同名','created_at':'2026-09-12T02:00:00Z'}]
    answer=agent.clarify(ResolutionError(field,'请选择',candidates),{})
    assert action in answer['suggested_actions']
    assert answer['choices'][0]['description']!=answer['choices'][1]['description']


@pytest.mark.parametrize('field,group,label,action',[('raster_id','rasters','新影像','add_raster'),('prompt_id','prompts','新样例','create_prompt')])
def test_new_resource_resumes_pending_task_without_reparsing(monkeypatch,env,field,group,label,action):
    ids=env[0]
    existing=env[1][group][0]
    env[1][group].append({**existing,'id':str(uuid4())})
    first=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='提取整个范围')
    assert first['field']==field and action in first['suggested_actions']
    new={**existing,'id':str(uuid4())}
    new['filename' if group=='rasters' else 'name']=label
    env[1][group].append(new)
    monkeypatch.setattr(agent,'parse_goal',lambda *args:pytest.fail('creation must resume original goal'))
    answer=agent.agent(ids['project'],agent.AgentRequest(text='已创建',continuation_id=first['continuation_id'],workspace_context={**first['context_update'],field:new['id']}),SimpleNamespace(user={'id':ids['user']}))
    assert answer['context_update'][field]==new['id']
    assert answer['kind']=='capability_unavailable'
    assert answer['goal']['requested_execution_scope']=='full_aoi'


def test_wrong_target_offers_covering_raster_without_redrawing_aoi(monkeypatch,env):
    ids=env[0];other={**env[1]['rasters'][0],'id':str(uuid4()),'filename':'Covering raster'};env[1]['rasters'].append(other)
    def coverage(p,u,r,a):
        if str(r)==ids['raster']:return {'available':False,'reason':'outside_raster','execution_mode':'single_tile_full_aoi','overlaps_raster':False}
        return {'available':True,'execution_mode':'single_tile_full_aoi','raster_id':str(r),'aoi_id':str(a),'query_col':0,'query_row':0,'aoi_revision':1}
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',coverage)
    first=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),text='分析整个AOI',raster_id=ids['raster'],aoi_id=ids['aoi'])
    assert first['field']=='raster_id' and first['choices'][0]['id']==other['id']
    answer=agent.agent(ids['project'],agent.AgentRequest(text='改用覆盖影像',continuation_id=first['continuation_id'],workspace_context={**first['context_update'],'raster_id':other['id']}),SimpleNamespace(user={'id':ids['user']}))
    assert answer['kind']=='draft' and answer['context_update']['aoi_id']==ids['aoi']
    assert answer['execution_mode']=='single_tile_full_aoi'


def test_product_test_request_requires_aoi_and_offers_creation(monkeypatch,env):
    env[1]['aois']=[]
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'))
    assert answer['kind']=='clarification' and answer['field']=='aoi_id'
    assert 'create_aoi' in answer['suggested_actions']
    assert 'select_window' not in answer['suggested_actions']


def test_large_aoi_never_offers_map_test_even_with_old_coordinates(monkeypatch,env):
    answer=run(monkeypatch,env,AgentGoal(goal_type='test_model_here',requested_execution_scope='single_tile'),query_col=0,query_row=0,window_source='map',aoi_id=env[0]['aoi'])
    assert answer['kind']=='capability_unavailable'
    assert answer['field']=='aoi_id' and 'create_aoi' in answer['suggested_actions']
    assert 'select_window' not in answer['suggested_actions']
    assert not any('llm:draft:' in key for key in env[-1])


def test_large_aoi_offers_only_compatible_alternative_ranges(monkeypatch,env):
    ids=env[0]
    compatible={'id':str(uuid4()),'name':'可一次分析','created_at':'2026-09-12T03:00:00Z'}
    incompatible={'id':str(uuid4()),'name':'其他影像范围','created_at':'2026-09-12T04:00:00Z'}
    env[1]['aois'].extend([compatible,incompatible])
    def coverage(project,user,raster,aoi):
        if str(aoi)==compatible['id']:
            return {'available':True,'execution_mode':'single_tile_full_aoi','query_col':0,'query_row':0,'aoi_revision':1,'aoi_id':str(aoi),'raster_id':str(raster),'aoi_bbox_width_px':200,'aoi_bbox_height_px':180}
        reason='outside_raster' if str(aoi)==incompatible['id'] else 'multi_tile_required'
        return {'available':False,'execution_mode':'multi_tile_full_aoi' if reason=='multi_tile_required' else 'unavailable','reason':reason,'aoi_bbox_width_px':930,'aoi_bbox_height_px':484}
    monkeypatch.setattr(agent.llm,'resolve_full_aoi',coverage)
    answer=run(monkeypatch,env,AgentGoal(goal_type='extract_similar',requested_execution_scope='full_aoi'),aoi_id=ids['aoi'])
    assert answer['kind']=='capability_unavailable'
    assert [choice['id'] for choice in answer['choices']]==[compatible['id']]
    assert '930 × 484' in answer['message']
    assert '512 × 512' in answer['labels']['能力状态']

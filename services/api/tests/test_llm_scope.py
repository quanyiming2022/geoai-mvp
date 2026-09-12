from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import HTTPException
from geoai import llm

@pytest.mark.parametrize('text',['用这个样例提取12aoi中所有的','提取12aoi中所有建筑','扫描整个AOI','extract the entire AOI'])
def test_full_aoi_intent_recognized(text):
    assert llm.requested_scope(text)=='full_aoi'

@pytest.mark.parametrize('text',['测试这里','在这个位置测试','single_tile','test here'])
def test_single_tile_intent_recognized(text):
    assert llm.requested_scope(text)=='single_tile'


def test_whole_area_cannot_be_built_even_with_coordinates():
    with pytest.raises(HTTPException) as error:
        llm.build_job(llm.Intent(intent='extract',execution_scope='full_aoi',query_col=0,query_row=0),{},uuid4())
    assert error.value.detail['code']=='CAPABILITY_NOT_AVAILABLE'


def test_full_aoi_blocked_before_llm_and_never_downgraded(monkeypatch):
    r,p,a,e=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
    resources={'rasters':[{'id':r,'filename':'SPOT'}],'prompts':[{'id':p,'name':'Building'}],'aois':[{'id':a,'name':'12aoi'}],'endpoints':[{'id':e,'model_name':'SkySense++'}]}
    monkeypatch.setattr(llm,'catalog',lambda *args:resources)
    monkeypatch.setattr(llm,'resolve_full_aoi',lambda *args:{'available':False,'execution_mode':'multi_tile_full_aoi','reason':'multi_tile_required'})
    monkeypatch.setattr(llm,'configuration',lambda:pytest.fail('Unavailable capability must not depend on LLM'))
    data=llm.PlanInput(text='用这个样例提取12aoi中所有的',workspace_context=llm.WorkspaceContext(channel='worker',raster_id=r,prompt_id=p,aoi_id=a,endpoint_id=e,query_col=0,query_row=0))
    answer=llm.plan(uuid4(),data,SimpleNamespace())
    assert answer['code']=='CAPABILITY_NOT_AVAILABLE' and answer['execution_scope']=='full_aoi'
    assert answer['labels']['AOI']=='12aoi' and answer['labels']['视觉样例']=='Building'
    assert not answer.get('draft_id')
    bound=llm.bind_workspace_intent(llm.Intent(intent='extract',execution_scope='full_aoi'),data.workspace_context)
    assert bound.execution_scope=='full_aoi' and bound.aoi_id==a


def test_no_implicit_zero_window():
    r,p,e,m=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
    data={'rasters':[{'id':r,'filename':'image','status':'ready','width':1024,'height':1024,'bands':3}],'prompts':[{'id':p,'name':'target','raster_asset_id':r}],'aois':[],'endpoints':[{'id':e,'model_name':'real','health_status':'healthy','name':'GPU','model_release_id':m,'config_revision':1,'usage_policy':'research_only'}]}
    intent=llm.Intent(intent='extract',channel='worker',raster_id=r,prompt_id=p,endpoint_id=e)
    with pytest.raises(HTTPException):llm.build_job(intent,data,uuid4())
    intent.query_col=0;intent.query_row=0
    job,labels=llm.build_job(intent,data,uuid4())
    assert job.kind=='geoextract_tile' and job.query_col==0
    assert labels['执行范围']=='单瓦片测试' and labels['能力状态']=='可用'


def test_map_selection_uses_geotransform_and_edge_clamping():
    import numpy as np
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin
    from geoai.map_window import select_window
    with MemoryFile() as memory:
        with memory.open(driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=from_origin(116,40,.0001,.0001)) as ds:
            ds.write(np.zeros((3,1024,1024),dtype='uint8'))
            picked=select_window(ds,116.06,39.94)
            assert picked['query_col'] in (343,344) and picked['query_row'] in (343,344)
            assert select_window(ds,116.00001,39.99999)['query_col']==0
            assert select_window(ds,116.1023,39.8977)['query_row']==512
            with pytest.raises(ValueError):select_window(ds,0,0)


def test_status_of_all_jobs_is_not_full_area_extraction():
    assert llm.requested_scope("查看所有任务状态") is None


def test_explicit_mock_diagnostic_is_not_whole_area_but_full_request_stays_blocked():
    assert llm.requested_scope('生成 Mock 提取测试任务草案')=='single_tile'
    assert llm.requested_scope('用 Mock 测试扫描整个 AOI')=='full_aoi'

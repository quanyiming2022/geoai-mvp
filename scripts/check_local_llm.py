"""Read-only local LLM check with synthetic catalog; does not create platform records."""
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from geoai.llm import HttpLLMProvider,Profile,Intent,SYSTEM,build_job,planner_schema

os.environ['LLM_LOCAL_URL']='http://127.0.0.1:11434'
r,p,a=map(str,(uuid4(),uuid4(),uuid4()))
resources={'rasters':[{'id':r,'filename':'fixture.tif','status':'ready','width':1024,'height':1024,'bands':3}], 'prompts':[{'id':p,'name':'草地样例','raster_asset_id':r}], 'aois':[{'id':a,'name':'验证范围'}], 'endpoints':[]}
checks=[]
for text,expected in [('请查看当前项目任务状态','status'),('使用 fixture.tif、草地样例和验证范围，生成 Mock 提取测试草案，明确使用 Mock。','extract'),('请自动绘制样例，然后扫描整幅影像并排除天然裸岩。','help')]:
    started=time.monotonic()
    raw=HttpLLMProvider(Profile(mode='local')).generate([{'role':'system','content':SYSTEM+json.dumps(planner_schema(resources),ensure_ascii=False)},{'role':'user','content':json.dumps({'request':text,'catalog':resources},ensure_ascii=False)}],planner_schema(resources))
    Path("artifacts/p9c-last-intent.json").write_text(raw)
    intent=Intent.model_validate_json(raw)
    assert intent.intent==expected,(expected,intent)
    if expected=='extract':
        job,labels=build_job(intent,resources,uuid4())
        assert job.kind=='geoextract' and str(job.raster_asset_id)==r
    checks.append({'request':text,'intent':intent.intent,'runtime_ms':round((time.monotonic()-started)*1000)})
    print('PASS',checks[-1],flush=True)
Path('artifacts/p9c-local-readonly.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))

# Contextual request: no resource names appear in the user instruction.
from geoai.llm import WorkspaceContext,context_resources,bind_workspace_intent
context=WorkspaceContext(channel='mock',raster_id=r,prompt_id=p,aoi_id=a)
selected=context_resources(context,resources);schema=planner_schema(selected);schema['properties']['channel']={'enum':['mock']}
started=time.monotonic()
raw=HttpLLMProvider(Profile(mode='local')).generate([{'role':'system','content':SYSTEM+json.dumps(schema,ensure_ascii=False)},{'role':'user','content':json.dumps({'request':'用这个样例提取当前范围','catalog':selected,'workspace_context':context.model_dump(mode='json')},ensure_ascii=False)}],schema)
intent=bind_workspace_intent(Intent.model_validate_json(raw),context)
assert intent.intent=='extract',intent
job,labels=build_job(intent,resources,uuid4())
assert str(job.raster_asset_id)==r and str(job.prompt_id)==p and str(job.aoi_id)==a
result={'request':'用这个样例提取当前范围','runtime_ms':round((time.monotonic()-started)*1000),'labels':labels,'job_created':False}
Path('artifacts/p9c-context-readonly.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('PASS: context-aware planning without repeated names',result,flush=True)

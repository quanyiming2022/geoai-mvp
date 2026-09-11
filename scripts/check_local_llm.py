"""Read-only local LLM check with synthetic catalog; does not create platform records."""
import json
import os
import time
from pathlib import Path
from uuid import uuid4
from geoai.llm import HttpLLMProvider,Profile,Intent,SYSTEM,build_job

os.environ['LLM_LOCAL_URL']='http://127.0.0.1:11434'
r,p,a=map(str,(uuid4(),uuid4(),uuid4()))
resources={'rasters':[{'id':r,'filename':'fixture.tif','status':'ready','width':1024,'height':1024,'bands':3}], 'prompts':[{'id':p,'name':'草地样例','raster_asset_id':r}], 'aois':[{'id':a,'name':'验证范围'}], 'endpoints':[]}
checks=[]
for text,expected in [('请查看当前项目任务状态','status'),('使用 fixture.tif、草地样例和验证范围，生成 Mock 提取测试草案，明确使用 Mock。','extract'),('请自动绘制样例，然后扫描整幅影像并排除天然裸岩。','help')]:
    started=time.monotonic()
    raw=HttpLLMProvider(Profile(mode='local')).generate([{'role':'system','content':SYSTEM+json.dumps(Intent.model_json_schema(),ensure_ascii=False)},{'role':'user','content':json.dumps({'request':text,'catalog':resources},ensure_ascii=False)}],Intent.model_json_schema())
    intent=Intent.model_validate_json(raw)
    assert intent.intent==expected,(expected,intent)
    if expected=='extract':
        job,labels=build_job(intent,resources,uuid4())
        assert job.kind=='geoextract' and str(job.raster_asset_id)==r
    checks.append({'request':text,'intent':intent.intent,'runtime_ms':round((time.monotonic()-started)*1000)})
    print('PASS',checks[-1],flush=True)
Path('artifacts/p9c-local-readonly.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))

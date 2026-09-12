"""Browser regression against the ordinary-owner acceptance_small_aoi fixture.
Run setup + login first; uses agent-browser session small-aoi. Never submits inference.
"""
import json,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=['pnpm','dlx','agent-browser@0.37.1','--session','small-aoi']
def browser(*args):
    r=subprocess.run(BASE+list(args),cwd=ROOT,text=True,capture_output=True,timeout=30)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout.strip()
def click(name):browser('find','role','button','click','--name',name,'--exact')
def js(code):return json.loads(browser('eval',code))
def wait_for(predicate,label):
    for _ in range(40):
        if predicate():return
        time.sleep(.25)
    raise AssertionError(label)
def body():return browser('get','text','body')
def point(x,y):
    browser('mouse','move',str(round(x)),str(round(y)));browser('mouse','down');browser('mouse','up')
def open_draw():
    if not js("document.querySelector('form:has(.extraction-steps) details').open"):browser('click','form:has(.extraction-steps) details > summary')
    click('在目标影像上绘制 AOI')
def draw(name):
    open_draw();browser('wait','1500')
    box=js("JSON.stringify(document.querySelector('.maplibregl-canvas').getBoundingClientRect().toJSON())")
    if isinstance(box,str):box=json.loads(box)
    x=box['x']+box['width']/2;y=box['y']+box['height']/2
    point(x-15,y-15);point(x+15,y+15)
    browser('find','role','textbox','fill','--name','名称','--exact',name);click('保存 AOI')
    wait_for(lambda:'关闭工作流' in body() and '3. 分析范围' in body(),'drawing must return to analysis step')
    wait_for(lambda:js("document.querySelector('input[name=aoi_id]')?.value")!='','new AOI selected')
    wait_for(lambda: name in browser('snapshot','-i'),'new AOI name visible in select')
    return name

def run():
    browser('set','viewport','1440','900')
    state=json.loads((ROOT/'artifacts/small-aoi-state.json').read_text())
    browser('open','http://127.0.0.1:3000/projects/'+state['project']+'/workspace')

    if '关闭工作流' in body():click('关闭工作流')
    browser('select','.extraction-launch select','worker');click('运行提取');click('下一步');click('下一步')
    expected=js("JSON.stringify(['raster_asset_id','prompt_id','model_endpoint_id'].map(n=>document.querySelector('input[name='+n+']').value))")
    open_draw();click('取消')
    assert '关闭工作流' in body() and '3. 分析范围' in body()
    assert js("document.querySelector('input[name=execution_scope]').value")=='full_aoi'
    draw('工作流完整范围-'+str(time.time_ns()))
    wait_for(lambda:'当前范围可一次完整分析' in body(),'automatic coverage')
    assert js("document.querySelector('input[name=execution_scope]').value")=='full_aoi'
    assert expected==js("JSON.stringify(['raster_asset_id','prompt_id','model_endpoint_id'].map(n=>document.querySelector('input[name='+n+']').value))")
    browser('screenshot',str(ROOT/'artifacts/workflow-return-full-1440.png'))
    browser('select','form:has(.extraction-steps) select',state['aois']['wide']['id'])
    wait_for(lambda:'请缩小 AOI' in body(),'large AOI blocked')
    assert '局部测试' not in browser('snapshot','-i')
    draw('工作流新小范围-'+str(time.time_ns()))
    wait_for(lambda:'当前范围可一次完整分析' in body(),'new range automatically covered')
    assert expected==js("JSON.stringify(['raster_asset_id','prompt_id','model_endpoint_id'].map(n=>document.querySelector('input[name='+n+']').value))")
    browser('set','viewport','1920','1080');browser('screenshot',str(ROOT/'artifacts/workflow-return-aoi-1920.png'))
    click('关闭工作流')
    assert not js("!!document.querySelector('.model-window-legend')")
    print('PASS: draw cancel/save returns to step 3 with resources preserved; large AOI requires smaller AOI; no window overlay; close works')
if __name__=='__main__':run()

"""Assistant lifecycle and Mock AOI creation regression on the isolated fixture."""
import json,time
from dotenv import dotenv_values
from acceptance_workflow_browser import ROOT,browser,click,js,point,wait_for,body


def open_assistant():
    wait_for(lambda:js("!!document.querySelector('.agent-launcher')"),'assistant launcher')
    browser('click','.agent-launcher')
    wait_for(lambda:js("!document.querySelector('#geoai-floating-agent').hidden"),'assistant opens')


def send(text):
    browser('fill','#agent-message',text)
    browser('press','Enter')
    wait_for(lambda:not js("document.querySelector('#agent-message').disabled"),'assistant response')


def draw_small_aoi(name):
    click('＋ 在目标影像上绘制 AOI')
    browser('wait','800')
    box=js("JSON.stringify(document.querySelector('.maplibregl-canvas').getBoundingClientRect().toJSON())")
    if isinstance(box,str):box=json.loads(box)
    x=box['x']+box['width']/2;y=box['y']+box['height']/2
    point(x-12,y-12);point(x+12,y+12)
    browser('find','role','textbox','fill','--name','名称','--exact',name)
    click('保存 AOI')
    wait_for(lambda:name in browser('snapshot','-i'),'new Mock AOI selected')


def verify_outside_aoi_is_not_saved():
    click('＋ 在目标影像上绘制 AOI')
    browser('wait','800')
    box=js("JSON.stringify(document.querySelector('.maplibregl-canvas').getBoundingClientRect().toJSON())")
    if isinstance(box,str):box=json.loads(box)
    # The raster is fitted with 30px padding; cross its left boundary so the
    # rectangle cannot be persisted as a workflow AOI for this raster.
    x=box['x'];y=box['y']+box['height']/2
    point(x+8,y-14);point(x+40,y+14)
    wait_for(lambda:'AOI 必须完整位于目标影像内' in body(),'outside AOI validation')
    assert js("[...document.querySelectorAll('button')].find(button=>button.textContent?.includes('保存 AOI'))?.disabled")
    click('重新绘制')
    assert 'AOI 必须完整位于目标影像内' not in body()
    click('取消')


def verify_large_in_bounds_aoi_is_not_saved():
    click('＋ 在目标影像上绘制 AOI')
    browser('wait','800')
    box=js("JSON.stringify(document.querySelector('.maplibregl-canvas').getBoundingClientRect().toJSON())")
    if isinstance(box,str):box=json.loads(box)
    # Workflow creation fits the 1280 px source into the map. This rectangle
    # remains inside the raster while spanning well over 512 source pixels.
    x=box['x']+box['width']/2;y=box['y']+box['height']/2
    point(x-box['width']*.28,y-box['height']*.08);point(x+box['width']*.28,y+box['height']*.08)
    name='MUST-NOT-PERSIST-'+str(time.time_ns())
    browser('find','role','textbox','fill','--name','名称','--exact',name)
    click('保存 AOI')
    wait_for(lambda:'超过单次 512 × 512 模型窗口' in body(),'large AOI capability preflight')
    assert '本次 AOI 未保存，请重新绘制' in body()
    assert not js(f"[...document.querySelectorAll('.spatial-resource-item .resource-row')].some(node=>node.textContent?.includes({json.dumps(name)}))")
    click('重新绘制')
    assert name not in js("[...document.querySelectorAll('.spatial-resource-item .resource-row')].map(node=>node.textContent).join('|')")
    click('取消')


def run():
    state=json.loads((ROOT/'artifacts/small-aoi-state.json').read_text())
    credentials=dotenv_values('/tmp/geoai-small-aoi-browser.env');email=credentials['EMAIL']
    url='http://127.0.0.1:3000/projects/'+state['project']+'/workspace'
    browser('open','http://127.0.0.1:3000/login');browser('set','viewport','1440','900')
    browser('find','role','textbox','fill','--name','邮箱','--exact',credentials['EMAIL'])
    browser('find','label','密码','fill',credentials['PASSWORD'])
    click('登录');wait_for(lambda:'我的项目' in body(),'isolated owner login')
    browser('open',url);wait_for(lambda:js("!!document.querySelector('.agent-launcher')"),'workspace ready')
    if '关闭工作流' in body():click('关闭工作流')
    assert '尚未选择对象' in body(), 'Workspace must not restore a transient raster selection'

    # Old active-session payloads from earlier releases must not be restored.
    storage=f'geoai-agent:{email}:{state["project"]}'
    stale=json.dumps({'history':[{'role':'user','text':'OLD-CONVERSATION'}]})
    js(f"sessionStorage.setItem({json.dumps(storage)},{json.dumps(stale)});localStorage.setItem({json.dumps(storage+':current')},{json.dumps(stale)});localStorage.removeItem({json.dumps(storage+':conversations')})")
    browser('reload');open_assistant()
    assert '从一个目标开始' in body() and 'OLD-CONVERSATION' not in body()
    assert js("document.querySelector('.agent-launcher').hidden")
    click('收起助手');assert not js("document.querySelector('.agent-launcher').hidden")

    # Closing the extraction workflow ends its assistant task; reopening starts fresh.
    open_assistant();send('刚才任务怎么样')
    assert '刚才任务怎么样' in body()
    click('收起助手')
    browser('select','.extraction-launch select','mock');click('运行提取')
    assert '＋ 在目标影像上绘制 AOI' in body()
    assert js("document.querySelector('form:has(h3) select[name=raster_asset_id]').value")==''
    assert js("document.querySelector('form:has(h3) select[name=aoi_id]').value")==''
    assert js("[...document.querySelectorAll('button')].find(button=>button.textContent?.includes('在目标影像上绘制 AOI'))?.disabled")
    browser('select','form:has(h3) select[name=raster_asset_id]',state['asset']['id'])
    wait_for(lambda:not js("[...document.querySelectorAll('button')].find(button=>button.textContent?.includes('在目标影像上绘制 AOI'))?.disabled"),'target raster selection')
    new_name='Mock 新范围-'+str(time.time_ns())
    draw_small_aoi(new_name)
    wait_for(lambda:js("document.querySelector('form:has(h3) select[name=aoi_id]').selectedOptions[0]?.textContent")==new_name,'Mock AOI selection survives refresh')
    verify_outside_aoi_is_not_saved()
    verify_large_in_bounds_aoi_is_not_saved()
    click('运行 Mock GeoExtract')
    wait_for(lambda:'Mock GeoExtract 已加入队列，可在底部任务栏查看进度。' in body(),'Mock submission feedback')
    wait_for(lambda:'任务已完成，结果已显示在地图上。' in body(),'manual completion feedback and result selection')
    if '关闭工作流' in body():click('关闭工作流')
    open_assistant()
    click('新建对话')
    assert '从一个目标开始' in body() and '刚才任务怎么样' not in body()
    click('历史对话 · 1')
    js("window.confirm=()=>true")
    browser('find','role','button','click','--name','删除历史对话“刚才任务怎么样”','--exact')
    wait_for(lambda:'历史对话 · 0' in body(),'initial archived conversation deletion')
    click('历史对话 · 0')

    # Leaving and re-entering Workspace also starts a fresh active conversation.
    send('刚才任务怎么样')
    browser('open','http://127.0.0.1:3000/control/projects')
    browser('open',url);open_assistant()
    assert '从一个目标开始' in body() and '刚才任务怎么样' not in body()
    send('刚才任务怎么样')
    click('新建对话');click('历史对话 · 1')
    js("window.confirm=()=>true")
    browser('find','role','button','click','--name','删除历史对话“刚才任务怎么样”','--exact')
    wait_for(lambda:'历史对话 · 0' in body(),'archived conversation deletion')
    print('PASS: no stale selection restore, target raster and AOI require explicit selection, Mock-created AOI is selected, manual completion selects and displays its result, outside and oversized AOIs are blocked before save, archived history can be deleted, re-entry starts fresh')


if __name__=='__main__':run()

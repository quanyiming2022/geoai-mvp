"""AOI-only product workflow. Isolated acceptance_small_aoi fixture; no inference submission."""
import json,re,time
from acceptance_workflow_browser import ROOT,browser,click,js,wait_for,draw

def no_point_mode():
    snapshot=browser('snapshot','-i')
    assert '局部测试' not in snapshot and '在地图上选择测试位置' not in snapshot
    assert not js("!!document.querySelector('.model-window-legend')")

def ask(text):
    browser('fill','#agent-message',text);browser('press','Enter')
    wait_for(lambda:not js("document.querySelector('#agent-message').disabled"),'assistant response')

def run():
    state=json.loads((ROOT/'artifacts/small-aoi-state.json').read_text())
    browser('open','http://127.0.0.1:3000/projects/'+state['project']+'/workspace')
    browser('set','viewport','1440','900')
    browser('select','.extraction-launch select','worker');click('运行提取')
    selector='form:has(.extraction-steps) select'
    click('下一步');click('下一步')
    browser('select',selector,state['aois']['small']['id'])
    wait_for(lambda:js("document.querySelector('input[name=query_col]').value")!='','automatic small AOI')
    no_point_mode();click('下一步');click('下一步')
    assert '分析整个 AOI' in browser('snapshot','-i')
    click('上一步');click('上一步')
    browser('select',selector,state['aois']['wide']['id'])
    wait_for(lambda:'请缩小 AOI' in browser('get','text','body'),'large AOI explained')
    assert js("[...document.querySelectorAll('button')].find(b=>b.textContent==='下一步').disabled")
    no_point_mode();browser('screenshot',str(ROOT/'artifacts/aoi-only-large-1440.png'))
    draw('AOI-only-'+str(time.time_ns()))
    wait_for(lambda:js("document.querySelector('input[name=query_col]').value")!='','saved drawing resumes automatic coverage')
    no_point_mode();click('关闭工作流')
    click('AOI');click('宽度超限范围 5.13 ha');browser('click','.agent-launcher')
    ask('用这个样例测试这里')
    wait_for(lambda:'在地图上绘制 AOI' in browser('snapshot','-i'),'large AOI offers creation')
    no_point_mode()
    # The new range must continue the same pending intent rather than reparse a command.
    click('在地图上绘制 AOI');browser('wait','1200')
    box=js("JSON.stringify(document.querySelector('.maplibregl-canvas').getBoundingClientRect().toJSON())")
    if isinstance(box,str):box=json.loads(box)
    from acceptance_workflow_browser import point
    x=box['x']+box['width']/2;y=box['y']+box['height']/2
    point(x-10,y-10);point(x+10,y+10)
    browser('find','role','textbox','fill','--name','名称','--exact','助手小范围-'+str(time.time_ns()))
    click('保存 AOI')
    wait_for(lambda:'开始分析' in browser('snapshot','-i'),'assistant resumes confirmation')
    no_point_mode();browser('set','viewport','1920','1080')
    browser('screenshot',str(ROOT/'artifacts/aoi-only-assistant-1920.png'))
    click('取消');browser('reload');browser('click','.agent-launcher');no_point_mode()
    print('PASS: small AOI confirmation, large AOI blocked with create recovery, manual drawing continuation, assistant new AOI resumes same goal, no local-test controls/overlay at 1440/1920; no inference submitted')
if __name__=='__main__':run()

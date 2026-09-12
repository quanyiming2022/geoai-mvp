"""Standalone local annotation artifact, not a GeoAI product page. No model predictions."""
import base64,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
root=ROOT/'artifacts/p10';queries=json.loads((root/'candidate-manifest.json').read_text())
for q in queries:q['image']='data:image/png;base64,'+base64.b64encode((root/'candidates'/q['query_id']/'query.png').read_bytes()).decode()
page='''<!doctype html><meta charset="utf-8"><title>P10 建筑标注</title><style>body{font:15px sans-serif;margin:20px;color:#18382e}main{display:flex;gap:24px}canvas{border:1px solid #777;width:512px;height:512px;cursor:crosshair}button,input,select{margin:4px;padding:8px}aside{max-width:440px}#status{white-space:pre-wrap}</style>
<h1>P10 建筑 GT · 人工标注包</h1><p>仅输入影像，无模型预测。此工具不会自动生成或批准任何 GT。数据仅保存在当前浏览器本地，完成后请导出文件。</p>
<div><button onclick="step(-1)">上一张</button><select id="query" onchange="load(+this.value)"></select><button onclick="step(1)">下一张</button><b id="name"></b></div>
<main><canvas id="canvas" width="512" height="512"></canvas><aside>
<p>逐个沿建筑屋顶轮廓点击顶点，点击“完成轮廓”闭合。不确定是否为建筑的区域请标为 ignore。不要把露营车、阴影、道路等仅凭亮度当作建筑。必须覆盖整张图中的所有建筑后，才能标记完整。</p>
<select id="kind"><option value="building">建筑</option><option value="ignore">不确定 / 忽略区域</option></select><br>
<button onclick="finish()">完成轮廓</button><button onclick="points.pop();draw()">撤销顶点</button><button onclick="removeLast()">删除最后轮廓</button><br>
<label>复核人 <input id="reviewer" placeholder="填写实际复核人"></label><br>
<label><input id="reviewed" type="checkbox" onchange="approve()">已完整检查此图全部建筑和忽略区域</label>
<p>没有建筑也必须逐图检查后再标记完整。未复核的空标注不是负样本 GT。</p>
<button onclick="download()">导出全部标注 JSON</button><p id="status"></p>
</aside></main><script>
const queries=__DATA__,key='geoai-p10-annotation-v1';let index=0,points=[],image=new Image();let labels={};try{labels=JSON.parse(localStorage.getItem(key)||'{}')}catch{}
const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d'),select=document.getElementById('query');queries.forEach((q,i)=>select.add(new Option(q.query_id+' · '+q.scene_type_provisional,i)));
function item(){return labels[queries[index].query_id]??={polygons:[],reviewer:null,reviewed_at:null,complete:false}}
function persist(){try{localStorage.setItem(key,JSON.stringify(labels))}catch{alert('本地存储不足，请立即导出文件')}}
function draw(){ctx.clearRect(0,0,512,512);ctx.drawImage(image,0,0);for(const p of [...item().polygons,{kind:document.getElementById('kind').value,points}]){if(!p.points.length)continue;ctx.beginPath();p.points.forEach(([x,y],i)=>i?ctx.lineTo(x,y):ctx.moveTo(x,y));if(p!==undefined&&p.points!==points)ctx.closePath();ctx.strokeStyle=p.kind==='building'?'#ff3030':'#ffd000';ctx.lineWidth=1.5;ctx.stroke()}document.getElementById('status').textContent='轮廓 '+item().polygons.length+'\n完成复核 '+Object.values(labels).filter(x=>x.complete).length+' / '+queries.length}
function load(i){index=Math.max(0,Math.min(queries.length-1,i));points=[];select.value=index;document.getElementById('name').textContent=queries[index].query_id;document.getElementById('reviewed').checked=item().complete;document.getElementById('reviewer').value=item().reviewer||'';image.onload=draw;image.src=queries[index].image}
function step(delta){if(points.length&&!confirm('放弃当前未闭合轮廓？'))return;load(index+delta)}
canvas.onclick=e=>{const b=canvas.getBoundingClientRect();points.push([(e.clientX-b.left)*512/b.width,(e.clientY-b.top)*512/b.height]);draw()};
function dirty(){item().complete=false;item().reviewed_at=null;document.getElementById('reviewed').checked=false;persist();draw()}
function finish(){if(points.length<3)return;item().polygons.push({kind:document.getElementById('kind').value,points:[...points]});points=[];dirty()}
function removeLast(){item().polygons.pop();dirty()}
function approve(){const r=document.getElementById('reviewer').value.trim();if(!r||points.length){document.getElementById('reviewed').checked=false;alert('请填写复核人，并先完成或撤销当前轮廓');return}item().complete=document.getElementById('reviewed').checked;item().reviewer=r;item().reviewed_at=item().complete?new Date().toISOString():null;persist();draw()}
function download(){const data={schema_version:1,coordinate_space:'query_pixel',queries:queries.map(({image,...q})=>({...q,annotation:labels[q.query_id]||null}))};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download='p10-building-annotations.json';a.click();URL.revokeObjectURL(a.href)}load(0);
</script>'''
(root/'annotation-tool.html').write_text(page.replace('__DATA__',json.dumps(queries,ensure_ascii=False)))
print('Prepared standalone annotation packet; all GT remains unapproved')

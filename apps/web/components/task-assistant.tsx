"use client";
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {languageRequest} from '../app/control/models/language/actions';
import type {AvailableEndpoint} from './tile-extraction-form';
export type AssistantContext={channel:'mock'|'worker';raster_id?:string;prompt_id?:string;aoi_id?:string;endpoint_id?:string;query_col?:number;query_row?:number};
type Named={id:string;name:string};
type Answer={kind:string;message:string;draft_id?:string;labels?:Record<string,string>;jobs?:{id:string;status:string;progress:number}[];runtime_ms:number;llm_model:string;contextKey:string};
export default function TaskAssistant({projectId,editable,onConfirmed,context,onContextChange,onPickWindow,rasters,prompts,aois,endpoints}:{projectId:string;editable:boolean;onConfirmed?:()=>void;context:AssistantContext;onContextChange:(c:AssistantContext)=>void;onPickWindow:()=>void;rasters:{id:string;filename:string;status:string}[];prompts:Named[];aois:Named[];endpoints:AvailableEndpoint[]}){
 const router=useRouter();const [text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[answer,setAnswer]=useState<Answer|null>(null),[external,setExternal]=useState(false),[consentKey,setConsentKey]=useState<string|null>(null);
 const contextKey=JSON.stringify(context);const allow=consentKey===contextKey;const stale=!!answer&&answer.contextKey!==contextKey;
 useEffect(()=>{let active=true;languageRequest('/llm/availability',undefined,'GET').then(r=>{if(active&&r.data)setExternal(r.data.external);});return()=>{active=false;};},[]);
 function update(value:Partial<AssistantContext>){onContextChange({...context,...('raster_id' in value?{query_col:undefined,query_row:undefined}:{}),...value});setAnswer(null);setConsentKey(null);setError('');}
 async function plan(){const consent=allow;const submittedKey=contextKey;setConsentKey(null);setBusy(true);setError('');setAnswer(null);try{const r=await languageRequest(`/projects/${projectId}/assistant/plan`,{text,workspace_context:context,allow_external_metadata:consent});if(r.error)setError(r.error);else setAnswer({...r.data,contextKey:submittedKey});}finally{setBusy(false);}}
 async function confirm(){if(!answer?.draft_id||stale)return;setBusy(true);setError('');try{const r=await languageRequest(`/projects/${projectId}/assistant/confirm`,{draft_id:answer.draft_id,confirmed:true});if(r.error)setError(r.error);else{setText('');setAnswer(null);onConfirmed?.();router.push(`/projects/${projectId}/workspace?job=${r.data.id}&message=${encodeURIComponent('已确认并创建任务，任务将在后台继续运行。')}`);router.refresh();}}finally{setBusy(false);}}
 const choice=(field:'raster_id'|'prompt_id'|'aoi_id'|'endpoint_id',label:string,items:Named[])=><label>{label}<select disabled={busy} value={context[field]??''} onChange={e=>update({[field]:e.target.value||undefined})}><option value="">{items.length?'请选择':'暂无可用对象'}</option>{items.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label>;
 return <section className="task-assistant"><h3>自然语言任务助手</h3><p>已带入工作区选择。描述操作，核对草案后再运行。</p>
 <form onSubmit={e=>{e.preventDefault();void plan();}}><fieldset className="assistant-context"><legend>当前选择</legend><small>沿用工作区选择；仅有一个可用对象时自动带入。多个对象未选时请明确选择。</small>
 {choice('raster_id','影像',rasters.filter(r=>r.status==='ready').map(r=>({id:r.id,name:r.filename})))}
 {choice('prompt_id','视觉样例',prompts)}
 <label>计算通道<select disabled={busy} value={context.channel} onChange={e=>update({channel:e.target.value as AssistantContext['channel']})}><option value="mock">Mock · 合成流程验证</option><option value="worker">真实 Worker · 单瓦片</option></select></label>
 {choice('aoi_id','AOI 搜索范围',aois)}
 {context.channel==='worker'&&<>{choice('endpoint_id','模型与计算节点',endpoints.filter(e=>e.health_status==='healthy').map(e=>({id:e.id,name:`${e.model_name} · ${e.name} · ${e.usage_policy==='research_only'?'仅研究用途':e.usage_policy}`})))}<p>{context.query_col!==undefined&&context.query_row!==undefined?'已在地图选择单瓦片测试区域':'尚未选择单瓦片测试区域'}</p><button type="button" className="secondary" disabled={busy||!context.raster_id} onClick={onPickWindow}>在地图上选择单瓦片测试区域</button><small>固定 512×512 原分辨率像素；AOI 是上下文，不代表已支持全范围扫描。</small></>}
 {!prompts.length&&<p>请先在地图创建并保存视觉样例。文字描述不会自动生成掩膜。</p>}</fieldset>
 <label>任务描述<textarea value={text} maxLength={2000} rows={3} disabled={busy} onChange={e=>{setText(e.target.value);setAnswer(null);setConsentKey(null);}} placeholder="用这个样例提取当前范围；或查看当前项目任务状态"/></label>
 {external&&<label className="inline-check"><input type="checkbox" checked={allow} onChange={e=>setConsentKey(e.target.checked?contextKey:null)}/>同意本次将文本与所选资源元数据发送到已配置的云端服务</label>}
 <button className="secondary" disabled={busy||!text.trim()||external&&!allow}>{busy?'正在处理…':'生成任务草案'}</button></form>
 {error&&<p role="alert" className="notice">{error}</p>}{answer&&<div className="assistant-answer"><p>{answer.message}</p>{stale&&<p role="alert">工作区选择已变化，请重新生成草案后再确认。</p>}{answer.labels&&<dl>{Object.entries(answer.labels).map(([key,value])=><div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>}{answer.jobs?.map((job,i)=><p key={job.id}>任务 {i+1} · {job.status} · {Math.round(job.progress)}%</p>)}{answer.kind==='capability_unavailable'&&<><button className="secondary" disabled={!context.raster_id} onClick={()=>{setAnswer(null);setText('在这个位置测试');onPickWindow();}}>在地图上选择单瓦片测试区域</button><button className="secondary" onClick={()=>setAnswer(null)}>取消</button></>}{answer.kind==='status'&&!answer.jobs?.length&&<p>暂无任务。</p>}<small>{answer.llm_model} · {answer.runtime_ms} ms</small>{answer.draft_id&&<><p className="notice">尚未创建任务。LLM 仅填写参数，不参与像素分割，请核对资源与范围。</p><button disabled={!editable||busy||stale} onClick={()=>void confirm()}>确认并创建任务</button><button className="secondary" disabled={busy} onClick={()=>setAnswer(null)}>丢弃草案</button></>}</div>}
 <small>手动工作流始终保留；自动标注、全图扫描、语言排除和自动审核尚未开放。</small></section>;
}

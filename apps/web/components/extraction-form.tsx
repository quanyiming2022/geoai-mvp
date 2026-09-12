"use client";
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useFormStatus } from 'react-dom';
import { createExtractionJob } from '../app/actions';
import type { Aoi, VisualPrompt } from './project-map';
import type { RasterAsset } from '../lib/session';
function Submit({disabled}:{disabled:boolean}) { const {pending}=useFormStatus(); return <button disabled={disabled||pending}>{pending?'正在提交…':'运行 Mock GeoExtract'}</button>; }
export default function ExtractionForm({projectId,prompts,aois,rasters,idempotencyKey}:{projectId:string;prompts:VisualPrompt[];aois:Aoi[];rasters:RasterAsset[];idempotencyKey:string}) {
 const router=useRouter();
 const [selected,setSelected]=useState(prompts[0]?.id ?? '');
 const [rasterId,setRasterId]=useState('');
 const [aoiId,setAoiId]=useState('');
 const [notice,setNotice]=useState<{kind:'success'|'error';message:string}|null>(null);
 const prompt=prompts.find(p=>p.id===selected);
 useEffect(()=>{const created=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail.kind==='aoi')setAoiId(detail.id);};window.addEventListener('workspace-resource-created',created);return()=>window.removeEventListener('workspace-resource-created',created);},[]);
 const readyRasters=rasters.filter(r=>r.status==='ready');
 return <form action={async data=>{setNotice(null);const response=await createExtractionJob(data);if(response.error||!response.data){setNotice({kind:'error',message:response.error??'任务未创建，请重试。'});return;}setNotice({kind:'success',message:'Mock GeoExtract 已加入队列，可在底部任务栏查看进度。'});window.dispatchEvent(new CustomEvent('workspace-job-submitted',{detail:response.data}));router.refresh();}}><h3>Mock GeoExtract</h3><p className="muted">使用模拟模型验证流程。视觉样例可来自另一景影像。</p><input type="hidden" name="project_id" value={projectId}/><input type="hidden" name="idempotency_key" value={idempotencyKey}/><label>目标影像<select name="raster_asset_id" value={rasterId} onChange={e=>{setRasterId(e.target.value);setAoiId('');setNotice(null);window.dispatchEvent(new CustomEvent('workspace-target-raster',{detail:{rasterId:e.target.value}}));}} required><option value="">请选择目标影像</option>{readyRasters.map(r=><option key={r.id} value={r.id}>{r.filename}</option>)}</select></label><label>Visual Prompt<select name="prompt_id" value={selected} onChange={e=>{setSelected(e.target.value);setNotice(null);}} required>{prompts.map(p=><option key={p.id} value={p.id}>{p.name} · {p.class_label}</option>)}</select></label>{prompt&&<small>样例来源：{rasters.find(r=>r.id===prompt.raster_asset_id)?.filename??'已保存影像'}</small>}<label>AOI<select name="aoi_id" value={aoiId} onChange={e=>{setAoiId(e.target.value);setNotice(null);}} required><option value="">请选择 AOI</option>{aois.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><button type="button" className="secondary" disabled={!rasterId} onClick={()=>window.dispatchEvent(new CustomEvent('workspace-agent-ui',{detail:{action:'create_aoi',origin:'manual',raster_id:rasterId}}))}>＋ 在目标影像上绘制 AOI</button>{!rasterId?<p role="status">请先选择要分析的目标影像。</p>:!aoiId&&<p role="status">请选择已有 AOI，或在目标影像上绘制一个新范围。</p>}{notice&&<p role={notice.kind==='error'?'alert':'status'}>{notice.message}</p>}<Submit disabled={!rasterId || !prompt || !aoiId}/></form>;
}

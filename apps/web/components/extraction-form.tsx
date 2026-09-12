"use client";
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useFormStatus } from 'react-dom';
import { createExtractionJob } from '../app/actions';
import type { Aoi, VisualPrompt } from './project-map';
function Submit({disabled}:{disabled:boolean}) { const {pending}=useFormStatus(); return <button disabled={disabled||pending}>{pending?'正在提交…':'运行 Mock GeoExtract'}</button>; }
export default function ExtractionForm({projectId,prompts,aois,idempotencyKey}:{projectId:string;prompts:VisualPrompt[];aois:Aoi[];idempotencyKey:string}) {
 const router=useRouter();
 const [selected,setSelected]=useState(prompts[0]?.id ?? '');
 const [aoiId,setAoiId]=useState(aois[0]?.id ?? '');
 const [notice,setNotice]=useState<{kind:'success'|'error';message:string}|null>(null);
 const prompt=prompts.find(p=>p.id===selected);
 useEffect(()=>{const created=(event:Event)=>{const detail=(event as CustomEvent).detail;if(detail.kind==='aoi')setAoiId(detail.id);};window.addEventListener('workspace-resource-created',created);return()=>window.removeEventListener('workspace-resource-created',created);},[]);
 return <form action={async data=>{setNotice(null);const response=await createExtractionJob(data);if(response.error){setNotice({kind:'error',message:response.error});return;}setNotice({kind:'success',message:'Mock GeoExtract 已加入队列，可在底部任务栏查看进度。'});router.refresh();}}><h3>Mock GeoExtract</h3><p className="muted">使用模拟模型验证流程，生成测试候选斑块。</p><input type="hidden" name="project_id" value={projectId}/><input type="hidden" name="idempotency_key" value={idempotencyKey}/><input type="hidden" name="raster_asset_id" value={prompt?.raster_asset_id ?? ''}/><label>Visual Prompt<select name="prompt_id" value={selected} onChange={e=>{setSelected(e.target.value);setNotice(null);}} required>{prompts.map(p=><option key={p.id} value={p.id}>{p.name} · {p.class_label}</option>)}</select></label><label>AOI<select name="aoi_id" value={aoiId} onChange={e=>{setAoiId(e.target.value);setNotice(null);}} required><option value="">请选择 AOI</option>{aois.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><button type="button" className="secondary" disabled={!prompt} onClick={()=>window.dispatchEvent(new CustomEvent('workspace-agent-ui',{detail:{action:'create_aoi',origin:'manual',raster_id:prompt?.raster_asset_id}}))}>＋ 在地图上绘制 AOI</button>{!aoiId&&<p role="status">请选择已有 AOI，或在样例源影像上绘制一个新范围。</p>}{notice&&<p role={notice.kind==='error'?'alert':'status'}>{notice.message}</p>}<Submit disabled={!prompt || !aoiId}/></form>;
}

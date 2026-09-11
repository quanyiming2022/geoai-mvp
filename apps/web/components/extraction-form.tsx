"use client";
import { useState } from 'react';
import { useFormStatus } from 'react-dom';
import { createExtractionJob } from '../app/actions';
import type { Aoi, VisualPrompt } from './project-map';
function Submit({disabled}:{disabled:boolean}) { const {pending}=useFormStatus(); return <button disabled={disabled||pending}>{pending?'正在提交…':'运行 Mock GeoExtract'}</button>; }
export default function ExtractionForm({projectId,prompts,aois,idempotencyKey}:{projectId:string;prompts:VisualPrompt[];aois:Aoi[];idempotencyKey:string}) {
 const [selected,setSelected]=useState(prompts[0]?.id ?? '');
 const prompt=prompts.find(p=>p.id===selected);
 return <form action={createExtractionJob}><h3>Mock GeoExtract</h3><p className="muted">使用模拟模型验证流程，生成测试候选斑块。</p><input type="hidden" name="project_id" value={projectId}/><input type="hidden" name="idempotency_key" value={idempotencyKey}/><input type="hidden" name="raster_asset_id" value={prompt?.raster_asset_id ?? ''}/><label>Visual Prompt<select name="prompt_id" value={selected} onChange={e=>setSelected(e.target.value)} required>{prompts.map(p=><option key={p.id} value={p.id}>{p.name} · {p.class_label}</option>)}</select></label><label>AOI<select name="aoi_id" required>{aois.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label><Submit disabled={!prompt || !aois.length}/></form>;
}

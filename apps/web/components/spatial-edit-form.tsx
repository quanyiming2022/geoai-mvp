"use client";
import {useState} from 'react';
import {useRouter} from 'next/navigation';
import {editSpatialObject} from '../app/actions';
import PromptPreview from './prompt-preview';
import type {Aoi,VisualPrompt} from './project-map';
export default function SpatialEditForm({projectId,object,geometry,onSaved}:{projectId:string;object:Aoi|VisualPrompt;geometry:string;onSaved:()=>void}) {
 const router=useRouter();const [pending,setPending]=useState(false),[error,setError]=useState('');
 const prompt='raster_asset_id' in object;
 return <form onSubmit={async event=>{event.preventDefault();setPending(true);setError('');const data=new FormData(event.currentTarget);try{const result=await editSpatialObject(projectId,prompt?'prompts':'aois',object.id,data);if(result.error)setError(result.error);else{onSaved();router.refresh();}}catch{setError('保存结果未确认，请刷新核对当前版本后重试。');}finally{setPending(false);}}}>
 <input type="hidden" name="expected_revision" value={object.revision}/><input type="hidden" name="geometry" value={geometry}/>
 <label>名称<input name="name" defaultValue={object.name} required maxLength={120} disabled={pending}/></label>
 <label>描述<textarea name="description" defaultValue={object.description} maxLength={2000} disabled={pending}/></label>
 {prompt&&<><input type="hidden" name="raster_asset_id" value={object.raster_asset_id}/><label>目标类别<input name="class_label" defaultValue={object.class_label} maxLength={120} disabled={pending}/></label>{geometry&&<PromptPreview key={geometry} projectId={projectId} rasterId={object.raster_asset_id} geometry={geometry}/>}<small>保存时重新生成样例影像和二值掩膜；历史任务继续使用原版本。</small></>}
 {error&&<p role="alert">{error}</p>}<button className="secondary" disabled={pending||!geometry}>{pending?'正在保存并生成样例…':'保存修改'}</button></form>;
}

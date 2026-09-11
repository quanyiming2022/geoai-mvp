"use client";
import Image from 'next/image';
import { useEffect,useState } from 'react';
import { previewVisualPrompt } from '../app/actions';
export default function PromptPreview({projectId,rasterId,geometry}:{projectId:string;rasterId:string;geometry:string}) {
 const [preview,setPreview]=useState<{image?:string;mask?:string;error?:string}>({});
 const [pending,setPending]=useState(true);
 useEffect(()=>{let active=true;const timer=setTimeout(()=>{const data=new FormData();data.set('project_id',projectId);data.set('raster_asset_id',rasterId);data.set('geometry',geometry);previewVisualPrompt(data).then(result=>{if(active){setPreview(result);setPending(false);}}).catch(()=>{if(active){setPreview({error:'预览不可用'});setPending(false);}});},350);return()=>{active=false;clearTimeout(timer);};},[projectId,rasterId,geometry]);
 return <section className="prompt-preview"><h3>Prompt Preview</h3>{pending?<p role="status">正在生成样例预览…</p>:preview.error?<p role="alert">{preview.error}</p>:<div><Image unoptimized width={256} height={256} src={preview.image!} alt="样例影像预览"/><Image unoptimized width={256} height={256} src={preview.mask!} alt="目标二值掩膜预览"/></div>}<small>预览可缩放显示；真实模型使用源分辨率窗口。</small></section>;
}

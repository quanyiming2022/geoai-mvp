"use server";
import { api, ApiError } from '../../../lib/session';
import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
const get=(data:FormData,key:string)=>String(data.get(key) ?? '');
const id=(data:FormData)=>{const value=get(data,'id');if(value && !/^[0-9a-f-]{36}$/i.test(value))throw new Error('Invalid resource');return value;};
function errorMessage(error:unknown) { if(error instanceof ApiError && error.status===403)return '只有平台管理员可以配置模型服务器。';if(error instanceof ApiError && error.status===422)return '请检查局域网地址、模型版本和高级配置。';return '无法保存配置，请检查本地服务后重试。'; }
export async function saveEndpoint(data:FormData) {
 const resource=id(data);let message='';
 try { const existing=resource?(await api<Array<{id:string;auth_type:string;secret_ref:string|null}>>('/admin/model-endpoints')).find(e=>e.id===resource):undefined; await api('/admin/model-endpoints'+(resource?'/'+resource:''),{method:resource?'PUT':'POST',body:JSON.stringify({name:get(data,'name'),provider_type:get(data,'provider_type'),base_url:get(data,'base_url'),model_release_id:get(data,'model_release_id'),timeout_seconds:Number(get(data,'timeout_seconds')),enabled:data.has('enabled'),health_path:get(data,'health_path'),model_info_path:get(data,'model_info_path'),inference_path:get(data,'inference_path'),request_schema_version:'1',auth_type:existing?.auth_type??'none',secret_ref:existing?.secret_ref??null})}); }
 catch(error){message=errorMessage(error);}
 revalidatePath('/control/models');redirect('/control/models?tab=endpoints&message='+encodeURIComponent(message||'服务器配置已保存。'));
}
export async function saveRelease(data:FormData) {
 const resource=id(data);let message='';
 try { await api('/admin/models'+(resource?'/'+resource:''),{method:resource?'PUT':'POST',body:JSON.stringify({name:get(data,'name'),model_name:get(data,'model_name'),model_version:get(data,'model_version'),checkpoint_digest:get(data,'checkpoint_digest')||null,usage_policy:get(data,'usage_policy')})}); }
 catch(error){message=errorMessage(error);}
 revalidatePath('/control/models');redirect('/control/models?tab=models&message='+encodeURIComponent(message||'模型版本已保存。'));
}
export async function testEndpoint(data:FormData) {
 let message='';
 try { const result=await api<{status:string;code?:string}>('/admin/model-endpoints/'+id(data)+'/test',{method:'POST'});message=result.status==='healthy'?'服务器连接正常，模型身份已核对。':result.status==='offline'?'服务器离线，请检查地址、网络和远端服务。':'服务器响应异常或模型身份尚未匹配，请检查模型配置。'; }
 catch(error){message=errorMessage(error);}
 revalidatePath('/control/models');redirect('/control/models?tab=endpoints&message='+encodeURIComponent(message));
}
export async function deleteEndpoint(data:FormData) {
 let message='';
 try {await api('/admin/model-endpoints/'+id(data),{method:'DELETE'});}catch(error){message=errorMessage(error);}
 revalidatePath('/control/models');redirect('/control/models?tab=endpoints&message='+encodeURIComponent(message||'端点配置已移除，模型与项目数据已保留。'));
}

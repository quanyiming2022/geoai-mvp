"use server";
import {cookies} from 'next/headers';
import {requireUser} from '../../../../lib/session';
export async function languageRequest(path:string,body?:unknown,method='POST'){
 await requireUser();
 if(!(/^\/admin\/llm(?:\/test)?$/.test(path)||/^\/llm\/availability$/.test(path)||/^\/projects\/[0-9a-f-]{36}\/assistant\/(plan|confirm)$/.test(path)))throw new Error('Invalid assistant route');
 try{const response=await fetch(process.env.GEOAI_API_URL+path,{method,cache:'no-store',signal:AbortSignal.timeout(185000),headers:{'Content-Type':'application/json','Authorization':'Bearer '+(await cookies()).get('geoai-access')?.value},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)return {error:typeof data.detail==='string'?data.detail:'请求未完成，请检查配置或使用手动流程。'};return {data};}catch{return {error:'语言服务暂不可用或请求超时，手动工作流仍可使用。'};}
}

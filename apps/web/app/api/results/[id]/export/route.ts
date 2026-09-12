import {api,ApiError} from '../../../../../lib/session';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}){
 const {id}=await params;if(!/^[0-9a-f-]{36}$/i.test(id))return new Response('Invalid result',{status:400});
 try{const result=await api<{name:string}>(`/results/${id}/export`);const name=result.name.replace(/[\/\\\r\n]/g,'_').slice(0,120)||'提取结果';return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/geo+json','Content-Disposition':`attachment; filename="result.geojson"; filename*=UTF-8''${encodeURIComponent(name+'.geojson')}`,'Cache-Control':'no-store'}});}catch(error){return new Response('Export unavailable',{status:error instanceof ApiError?error.status:503});}
}

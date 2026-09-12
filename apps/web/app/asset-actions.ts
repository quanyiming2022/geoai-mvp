"use server";
import {api,ApiError} from '../lib/session';
export type LibraryAsset={id:string;name:string;filename:string;status:string;created_at:string;crs:string|null;width:number|null;height:number|null;bands:number|null;resolution:number[]|null;size:number;reference_count:number;can_manage:boolean};
const uuid=(v:string)=>/^[0-9a-f-]{36}$/i.test(v);
export async function listLibrary(search=''){return api<LibraryAsset[]>(`/raster-assets?limit=200&search=${encodeURIComponent(search)}`);}
export async function manageAsset(id:string,operation:'rename'|'delete'|'link'|'unlink'|'alias',name='',projectId=''){
 if(!uuid(id)||(['link','unlink','alias'].includes(operation)&&!uuid(projectId)))return {error:'无效资源。'};
 const path=operation==='link'||operation==='unlink'?`/projects/${projectId}/rasters/${id}/link`:operation==='alias'?`/projects/${projectId}/rasters/${id}`:`/raster-assets/${id}`;
 try {await api(path,{method:operation==='link'?'POST':operation==='delete'||operation==='unlink'?'DELETE':'PATCH',body:JSON.stringify(operation==='link'?{}:operation==='delete'||operation==='unlink'?{confirmed:true}:{name})});return {ok:true};}
 catch(error){return {error:error instanceof ApiError&&error.status===409?`该影像仍被 ${error.referenceCount??'其他'} 个项目使用，请先移除项目引用。`:error instanceof ApiError&&error.status===403?'你没有执行此操作的权限。':'操作未完成，请刷新后重试。'};}
}

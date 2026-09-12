"use server";
import {api,ApiError} from '../lib/session';
export async function manageResult(id:string,operation:'edit'|'delete',data:{expected_revision:number;result_name?:string;description?:string;geometry?:unknown}){
 if(!/^[0-9a-f-]{36}$/i.test(id))return {error:'无效结果。'};
 try{await api(`/results/${id}`,{method:operation==='delete'?'DELETE':'PATCH',body:JSON.stringify(operation==='delete'?{expected_revision:data.expected_revision,confirmed:true}:data)});return {ok:true};}
 catch(error){return {error:error instanceof ApiError&&error.status===409?'结果已被修改，请刷新后重试。':error instanceof ApiError&&error.status===403?'你没有编辑结果的权限。':'保存失败，请检查几何是否有效后重试。'};}
}

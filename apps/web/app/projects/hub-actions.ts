"use server";
import {api,type Project} from '../../lib/session';
export async function createHubProject(name:string,description:string):Promise<{id?:string;project?:Project;error?:string}>{try{const project=await api<Project>('/projects',{method:'POST',body:JSON.stringify({name,description})});return {id:project.id,project};}catch{return {error:'创建失败，请检查输入或稍后重试。'};}}

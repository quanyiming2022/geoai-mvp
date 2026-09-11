"use server";
import { api, ApiError, type Project } from '../../../lib/session';
export type SettingsMember={user_id:string;email:string|null;role:string;status:string};
export type SettingsResult={error?:string;project?:Project;members?:SettingsMember[]};
function path(id:string){if(!/^[0-9a-f-]{36}$/i.test(id))throw new Error('Invalid project');return `/projects/${id}`;}
function message(error:unknown){return error instanceof ApiError?({403:'你没有执行此操作的权限。',404:'未找到该账号或项目。',400:'成员已存在或输入无效。',409:'该账号已是项目所有者。'}[error.status]??'服务暂不可用，请重试。'):'操作未完成，请重试。';}
export async function saveSettings(id:string,name:string,description:string):Promise<SettingsResult>{try{return {project:await api<Project>(path(id),{method:'PATCH',body:JSON.stringify({name,description})})};}catch(e){return {error:message(e)};}}
export async function changeSettingsMember(id:string,mode:'add'|'change'|'remove',target:string,role:string):Promise<SettingsResult>{try{const base=path(id);if(mode!=='add'&&!/^[0-9a-f-]{36}$/i.test(target))return {error:'成员无效。'};await api(base+(mode==='add'?'/members/by-email':`/members/${target}`),{method:mode==='add'?'POST':mode==='remove'?'DELETE':'PATCH',body:mode==='remove'?undefined:JSON.stringify(mode==='add'?{email:target.trim(),role}:{role})});return {members:await api<SettingsMember[]>(base+'/member-identities')};}catch(e){return {error:message(e)};}}

export async function loadProjectSettings(id:string):Promise<SettingsResult>{try{const base=path(id);const [project,members]=await Promise.all([api<Project>(base),api<SettingsMember[]>(base+'/member-identities')]);return {project,members};}catch(e){return {error:message(e)};}}

export async function loadProjectOverview(id:string):Promise<{counts?:number[];error?:string}>{try{const base=path(id);await api<Project>(base);const [rasters,aois,prompts,results,jobs]=await Promise.all(['rasters','aois','prompts','results','jobs'].map(kind=>api<Array<{status?:string}>>(base+'/'+kind)));return {counts:[rasters.length,aois.length,prompts.length,results.length,jobs.filter(j=>j.status==='running'||j.status==='queued').length]};}catch(e){return {error:message(e)};}}

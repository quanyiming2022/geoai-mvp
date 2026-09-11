"use server";
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { revalidatePath } from 'next/cache';
import { api, ApiError, saveSession, type Session, type Project } from '../lib/session';

function value(data: FormData, key: string) { return String(data.get(key) ?? ''); }
function projectPath(data: FormData) {
  const id = value(data, 'project_id');
  if (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Invalid project');
  return `/projects/${id}`;
}
function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return '登录失败，请检查邮箱和密码。';
    if (error.status === 403) return '你没有执行此操作的权限。';
    if (error.status === 429) return '操作过于频繁，请稍后重试。';
    if (error.status === 400 || error.status === 422) return '请检查输入内容、用户 ID 或重复成员。';
  }
  return '服务暂不可用，请稍后重试。';
}
export async function authenticate(data: FormData) {
  const mode = value(data, 'mode') === 'signup' ? 'signup' : 'login';
  let message = '';
  try {
    const session = await api<Session>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email: value(data, 'email'), password: value(data, 'password') }) }, '');
    if (session.confirmation_required) message = '请查看邮箱并完成账号确认。';
    else await saveSession(session);
  } catch (error) { message = errorMessage(error); }
  if (message) redirect(`/login?message=${encodeURIComponent(message)}`);
  redirect('/projects');
}
export async function logout() {
  try { await api('/auth/logout', { method: 'POST' }); }
  catch (error) { if (!(error instanceof ApiError && error.status === 401)) redirect('/projects?message=' + encodeURIComponent('退出失败，请稍后重试。')); }
  const jar = await cookies(); jar.delete('geoai-access'); jar.delete('geoai-refresh');
  redirect('/login');
}
export async function createProject(data: FormData) {
  let id = ''; let message = '';
  try { const project = await api<Project>('/projects', { method: 'POST', body: JSON.stringify({ name: value(data, 'name'), description: value(data, 'description') }) }); id = project.id; }
  catch (error) { message = errorMessage(error); }
  if (message) redirect('/projects?message=' + encodeURIComponent(message));
  revalidatePath('/projects'); redirect(`/projects/${id}`);
}
export async function editProject(data: FormData) {
  const path = projectPath(data); let message = '';
  try { await api(path, { method: 'PATCH', body: JSON.stringify({ name: value(data, 'name'), description: value(data, 'description') }) }); }
  catch (error) { message = errorMessage(error); }
  revalidatePath(path); revalidatePath('/projects'); redirect(path + '?message=' + encodeURIComponent(message || '项目信息已保存。'));
}
export async function manageMember(data: FormData) {
  const path = projectPath(data); const mode = value(data, 'mode'); let message = '';
  const user = value(data, 'user_id');
  if (!/^[0-9a-f-]{36}$/i.test(user)) redirect(path + '?message=' + encodeURIComponent('请输入有效的用户 ID。'));
  const endpoint = `${path}/members` + (mode === 'add' ? '' : `/${user}`);
  const method = mode === 'add' ? 'POST' : mode === 'remove' ? 'DELETE' : 'PATCH';
  const body = mode === 'remove' ? undefined : JSON.stringify({ ...(mode === 'add' ? { user_id: user } : {}), role: value(data, 'role') });
  try { await api(endpoint, { method, body }); } catch (error) { message = errorMessage(error); }
  revalidatePath(path); redirect(path + '?message=' + encodeURIComponent(message || '成员权限已更新。'));
}

export async function retryRaster(data: FormData) {
  const path = projectPath(data); const id = value(data, 'asset_id');
  if (!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Invalid raster');
  let message = '';
  try { await api(`/rasters/${id}/retry`, { method: 'POST' }); } catch (error) { message = errorMessage(error); }
  revalidatePath(path + '/workspace');
  redirect(path + '/workspace' + (message ? '?message=' + encodeURIComponent(message) : ''));
}

export async function createAoi(data: FormData) {
  const path = projectPath(data); let message = '';
  try { await api(path + '/aois', { method: 'POST', body: JSON.stringify({ name: value(data, 'name'), geometry: JSON.parse(value(data, 'geometry')) }) }); }
  catch (error) { message = errorMessage(error); }
  revalidatePath(path + '/workspace');
  redirect(path + '/workspace?message=' + encodeURIComponent(message || 'AOI 已保存。'));
}

export async function createPrompt(data: FormData) {
  const path = projectPath(data); let message = '';
  try { await api(path + '/prompts', { method: 'POST', body: JSON.stringify({ name: value(data, 'name'), raster_asset_id: value(data, 'raster_asset_id'), class_label: value(data, 'class_label'), description: value(data, 'description'), geometry: JSON.parse(value(data, 'geometry')) }) }); }
  catch (error) { message = errorMessage(error); }
  revalidatePath(path + '/workspace');
  redirect(path + '/workspace?message=' + encodeURIComponent(message || 'Visual Prompt 已保存。'));
}

export async function createDiagnosticJob(data: FormData) {
 const path=projectPath(data); let message='';
 try { await api(path+'/jobs',{method:'POST',body:JSON.stringify({kind:'diagnostic',idempotency_key:value(data,'idempotency_key')})}); }
 catch(error) { message=errorMessage(error); }
 revalidatePath(path+'/workspace'); redirect(path+'/workspace?message='+encodeURIComponent(message || '任务已加入队列。'));
}
export async function controlJob(data: FormData) {
 const path=projectPath(data); const id=value(data,'job_id'); const action=value(data,'action'); let message='';
 if(!/^[0-9a-f-]{36}$/i.test(id) || !['cancel','retry'].includes(action)) throw new Error('Invalid job control');
 try { await api(`/jobs/${id}/${action}`,{method:'POST'}); } catch(error) { message=errorMessage(error); }
 revalidatePath(path+'/workspace'); redirect(path+'/workspace?message='+encodeURIComponent(message || '任务状态已更新。'));
}

export async function createExtractionJob(data: FormData) {
 const path=projectPath(data); let message='';
 try { await api(path+'/jobs',{method:'POST',body:JSON.stringify({kind:'geoextract',idempotency_key:value(data,'idempotency_key'),raster_asset_id:value(data,'raster_asset_id'),prompt_id:value(data,'prompt_id'),aoi_id:value(data,'aoi_id')})}); }
 catch(error) { message=errorMessage(error); }
 revalidatePath(path+'/workspace'); redirect(path+'/workspace?message='+encodeURIComponent(message || 'Mock GeoExtract 已加入队列。'));
}
export async function reviewResult(data: FormData) {
 const path=projectPath(data); const id=value(data,'result_id'); let message='';
 if(!/^[0-9a-f-]{36}$/i.test(id)) throw new Error('Invalid result');
 try { await api(`/results/${id}/review`,{method:'POST',body:JSON.stringify({action:value(data,'action')})}); } catch(error) { message=errorMessage(error); }
 const job=value(data,'job_id');
 revalidatePath(path+'/workspace'); redirect(path+'/workspace?'+(/^[0-9a-f-]{36}$/i.test(job)?'job='+job+'&':'')+'message='+encodeURIComponent(message || '审核已保存，原始预测已保留。'));
}

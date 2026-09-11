import { randomUUID } from 'node:crypto';
import ExtractionForm from '../../../../components/extraction-form';
import ResultsPanel from '../../../../components/results-panel';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import ProjectMap, { type Aoi, type VisualPrompt, type ExtractionResult } from '../../../../components/project-map';
import RasterUpload from '../../../../components/raster-upload';
import JobPanel, { type Job } from '../../../../components/job-panel';
import RasterPoll from '../../../../components/raster-poll';
import { retryRaster } from '../../../actions';
import { api, ApiError, type Project, type RasterAsset } from '../../../../lib/session';
export default async function Workspace({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ message?: string; job?: string; jobpage?: string }> }) {
 const { id } = await params; if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
 let project: Project;
 try { project = await api<Project>(`/projects/${id}`); } catch (error) { if (error instanceof ApiError && error.status === 404) notFound(); throw error; }
 const assets = await api<RasterAsset[]>(`/projects/${id}/rasters`);
 const aois = await api<Aoi[]>(`/projects/${id}/aois`);
 const prompts = await api<VisualPrompt[]>(`/projects/${id}/prompts`);
 const { message, job, jobpage } = await searchParams;
 const page = Math.min(20000,Math.max(0,Number.parseInt(jobpage ?? '0',10)||0));
 const selectedJob = job && /^[0-9a-f-]{36}$/i.test(job) ? job : undefined;
 const jobs = await api<Job[]>(`/projects/${id}/jobs?offset=${page*50}`);
 const results = await api<ExtractionResult[]>(`/projects/${id}/results${selectedJob ? '?job_id='+selectedJob : ''}`);
 return <>{message && <p role="status">{message}</p>}<RasterPoll pending={assets.some(a=>a.status === 'uploaded' || a.status === 'processing') || jobs.some(j=>j.status==='queued'||j.status==='running')}/><div className="workspace-heading"><div><Link href="/projects">← 所有项目</Link><h1>{project.name}</h1></div><Link className="settings-link" href={`/projects/${id}`}>项目信息与成员 →</Link></div><div className="map-workspace"><aside className="card layers-panel"><span className="eyebrow">项目工作空间</span><h2>项目影像</h2>{project.my_role !== 'viewer' && <RasterUpload projectId={id}/>}<div className="asset-list">{assets.length === 0 && <p className="muted">尚未上传影像。</p>}{assets.map(asset => <article className="asset-item" key={asset.id}><strong>{asset.filename}</strong><span>{(asset.size / 1024 / 1024).toFixed(2)} MiB · {({uploaded:'等待处理',processing:'正在处理',ready:'可用',failed:'处理失败'}[asset.status] ?? asset.status)}</span><span>{asset.crs} {asset.width && `${asset.width} × ${asset.height} · ${asset.bands} 波段`}</span>{asset.error_code && <span role="alert">{asset.error_code}</span>}{asset.status === 'failed' && project.my_role !== 'viewer' && <form action={retryRaster}><input type="hidden" name="project_id" value={id}/><input type="hidden" name="asset_id" value={asset.id}/><button className="secondary compact">重试处理</button></form>}<a href={`/api/rasters/${asset.id}/download`}>下载原始文件 ↗</a></article>)}</div><h3>地图图层</h3><div className="layer-item"><span className="layer-dot"/>经纬参考网</div><p className="muted">可用影像自动加入地图。底图为离线坐标画布。</p><p className="muted">拖动地图移动视野，使用右上角按钮或键盘 + / − 缩放。</p></aside><ProjectMap key={[...aois, ...prompts].map(a => a.id).join(',')} rasters={assets} aois={aois} prompts={prompts} results={results} projectId={id} editable={project.my_role !== 'viewer'}/></div>{project.my_role !== 'viewer' && <section className="card"><ExtractionForm key={prompts.map(p=>p.id).join(',')} prompts={prompts} aois={aois} projectId={id} idempotencyKey={randomUUID()}/></section>}<JobPanel page={page} jobs={jobs} projectId={id} editable={project.my_role !== 'viewer'}/><ResultsPanel results={results} projectId={id} editable={project.my_role !== 'viewer'}/></>;
}

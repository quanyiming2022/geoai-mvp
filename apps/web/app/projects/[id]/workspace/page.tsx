import { randomUUID } from 'node:crypto';
import TileExtractionForm, { type AvailableEndpoint } from '../../../../components/tile-extraction-form';
import ResultsPanel from '../../../../components/results-panel';
import ExtractionForm from '../../../../components/extraction-form';
import { notFound } from 'next/navigation';
import ProjectMap, { type Aoi, type VisualPrompt, type ExtractionResult } from '../../../../components/project-map';
import RasterUpload from '../../../../components/raster-upload';
import JobPanel, { type Job } from '../../../../components/job-panel';
import RasterPoll from '../../../../components/raster-poll';
import { retryRaster } from '../../../actions';
import { api, requireUser, ApiError, type Project, type RasterAsset } from '../../../../lib/session';
export default async function Workspace({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ message?: string; job?: string; jobpage?: string }> }) {
 const { id } = await params; if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
 let project: Project;
 try { project = await api<Project>(`/projects/${id}`); } catch (error) { if (error instanceof ApiError && error.status === 404) notFound(); throw error; }
 const user=await requireUser();
 const endpoints=await api<AvailableEndpoint[]>('/models/available-endpoints');
 const assets = await api<RasterAsset[]>(`/projects/${id}/rasters`);
 const aois = await api<Aoi[]>(`/projects/${id}/aois`);
 const prompts = await api<VisualPrompt[]>(`/projects/${id}/prompts`);
 const { message, job, jobpage } = await searchParams;
 const page = Math.min(20000,Math.max(0,Number.parseInt(jobpage ?? '0',10)||0));
 const selectedJob = job && /^[0-9a-f-]{36}$/i.test(job) ? job : undefined;
 const jobs = await api<Job[]>(`/projects/${id}/jobs?offset=${page*50}`);
 const results = await api<ExtractionResult[]>(`/projects/${id}/results${selectedJob ? '?job_id='+selectedJob : ''}`);
 return <>{message && <p role="status">{message}</p>}<RasterPoll monitorEndpoints pending={assets.some(a=>a.status === 'uploaded' || a.status === 'processing') || jobs.some(j=>j.status==='queued'||j.status==='running')}/><ProjectMap endpoints={endpoints} projectName={project.name} userEmail={user.email} hasHealthyEndpoint={endpoints.some(e=>e.health_status==='healthy')} jobs={jobs} key={[...aois,...prompts].map(p=>p.id).join(',')} rasters={assets} aois={aois} prompts={prompts} results={results} projectId={id} editable={project.my_role!=='viewer'} dataPanel={<>{project.my_role!=='viewer'&&<RasterUpload projectId={id}/>}{assets.filter(a=>a.status==='failed').map(asset=><form key={asset.id} action={retryRaster}><span>{asset.filename}: {asset.error_code}</span><input type="hidden" name="project_id" value={id}/><input type="hidden" name="asset_id" value={asset.id}/>{project.my_role!=='viewer'&&<button className="secondary">重试处理</button>}</form>)}</>} mockExtractionPanel={<ExtractionForm prompts={prompts} aois={aois} projectId={id} idempotencyKey={randomUUID()}/>} extractionPanel={<TileExtractionForm projectId={id} prompts={prompts} rasters={assets} endpoints={endpoints.filter(e=>e.health_status==='healthy')} idempotencyKey={randomUUID()}/>} resultsReviewPanel={<ResultsPanel results={results} projectId={id} editable={project.my_role!=='viewer'}/>} jobsPanel={<JobPanel page={page} jobs={jobs} projectId={id} editable={project.my_role!=='viewer'}/>}/></>;
}

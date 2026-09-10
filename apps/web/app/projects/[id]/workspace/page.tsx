import Link from 'next/link';
import { notFound } from 'next/navigation';
import ProjectMap from '../../../../components/project-map';
import { api, ApiError, type Project } from '../../../../lib/session';
export default async function Workspace({ params }: { params: Promise<{ id: string }> }) {
 const { id } = await params; if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
 let project: Project;
 try { project = await api<Project>(`/projects/${id}`); } catch (error) { if (error instanceof ApiError && error.status === 404) notFound(); throw error; }
 return <><div className="workspace-heading"><div><Link href="/projects">← 所有项目</Link><h1>{project.name}</h1></div><Link className="settings-link" href={`/projects/${id}`}>项目信息与成员 →</Link></div><div className="map-workspace"><aside className="card layers-panel"><span className="eyebrow">项目工作空间</span><h2>地图图层</h2><div className="layer-item"><span className="layer-dot"/>经纬参考网</div><p className="muted">当前使用离线坐标画布。影像上传后，可在这里管理项目图层。</p><p className="muted">拖动地图移动视野，使用右上角按钮或键盘 + / − 缩放。</p></aside><ProjectMap/></div></>;
}

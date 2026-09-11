import Link from 'next/link';
import { notFound } from 'next/navigation';
import ProjectMap from '../../../../components/project-map';
import RasterUpload from '../../../../components/raster-upload';
import { api, ApiError, type Project, type RasterAsset } from '../../../../lib/session';
export default async function Workspace({ params }: { params: Promise<{ id: string }> }) {
 const { id } = await params; if (!/^[0-9a-f-]{36}$/i.test(id)) notFound();
 let project: Project;
 try { project = await api<Project>(`/projects/${id}`); } catch (error) { if (error instanceof ApiError && error.status === 404) notFound(); throw error; }
 const assets = await api<RasterAsset[]>(`/projects/${id}/rasters`);
 return <><div className="workspace-heading"><div><Link href="/projects">← 所有项目</Link><h1>{project.name}</h1></div><Link className="settings-link" href={`/projects/${id}`}>项目信息与成员 →</Link></div><div className="map-workspace"><aside className="card layers-panel"><span className="eyebrow">项目工作空间</span><h2>项目影像</h2>{project.my_role !== 'viewer' && <RasterUpload projectId={id}/>}<div className="asset-list">{assets.length === 0 && <p className="muted">尚未上传影像。</p>}{assets.map(asset => <article className="asset-item" key={asset.id}><strong>{asset.filename}</strong><span>{(asset.size / 1024 / 1024).toFixed(2)} MiB · {asset.status === 'uploaded' ? '已上传' : asset.status}</span><a href={`/api/rasters/${asset.id}/download`}>下载原始文件 ↗</a></article>)}</div><h3>地图图层</h3><div className="layer-item"><span className="layer-dot"/>经纬参考网</div><p className="muted">上传的原始影像将在完成 COG 处理后加入地图。当前使用离线坐标画布。</p><p className="muted">拖动地图移动视野，使用右上角按钮或键盘 + / − 缩放。</p></aside><ProjectMap/></div></>;
}

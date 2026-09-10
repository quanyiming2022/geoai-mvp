import Link from 'next/link';
import { GET } from '../api/health/route';
export const dynamic = 'force-dynamic';
export default async function HealthPage() {
  const response = await GET();
  const health = await response.json() as { status: string; reason?: string; checks?: Record<string, string> };
  return <main className="workspace"><p className="eyebrow">GEOAI PLATFORM / HEALTH</p>
    <h1>{health.status === 'ok' ? '基础服务已就绪' : '基础服务尚未就绪'}</h1>
    <p>这是当前连通性检查，完整 P0 验收还包括测试和持久化重启验证。</p>
    <section>{health.reason && <p>{health.reason}</p>}
      {health.checks && <dl>{Object.entries(health.checks).map(([name, status]) =>
        <div key={name} style={{display: 'flex', justifyContent: 'space-between', padding: '8px 0'}}>
          <dt>{name}</dt><dd>{status}</dd></div>)}</dl>}
    </section><Link href="/">← 返回项目</Link></main>;
}

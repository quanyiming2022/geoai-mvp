import Link from 'next/link';
import { requireUser } from '../../lib/session';
import { logout } from '../actions';
export default async function ProjectsLayout({ children }: { children: React.ReactNode }) {
 const user = await requireUser();
 return <><header className="topbar"><Link className="wordmark" href="/projects">◈ GeoAI <span>Platform</span></Link><nav><Link href="/projects">项目</Link><Link href="/health">服务状态</Link><span>{user.email}</span><form action={logout}><button className="secondary compact">退出登录</button></form></nav></header><main className="workspace">{children}</main></>;
}

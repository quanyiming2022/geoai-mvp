import Link from 'next/link';
import { authenticate } from '../actions';
export default async function Login({ searchParams }: { searchParams: Promise<{ message?: string }> }) {
  const { message } = await searchParams;
  return <main className="auth-shell"><section className="brand-panel"><span className="eyebrow">GEOAI PLATFORM</span><h1>从地理数据，<br/>到空间洞察。</h1><p>面向遥感分析的协作工作空间。</p><Link href="/health">查看服务状态 ↗</Link></section><section className="card auth-card"><span className="eyebrow">欢迎回来</span><h2>进入你的工作空间</h2><p className="muted">登录或创建账号，开始管理项目。</p>{message && <p role="status" className="notice">{message}</p>}<form action={authenticate}><label>邮箱<input name="email" type="email" autoComplete="email" required maxLength={254}/></label><label>密码<input name="password" type="password" autoComplete="current-password" minLength={8} maxLength={128} required/></label><button name="mode" value="login">登录</button><button className="secondary" name="mode" value="signup">创建账号</button></form></section></main>;
}

import Link from 'next/link';
import {logout} from '../app/actions';
export default function PlatformHeader({email,isAdmin}:{email:string;isAdmin:boolean}){return <header className="topbar"><Link className="wordmark" href="/control/projects">◈ GeoAI <span>Platform</span></Link><nav><Link href="/control/projects">项目</Link><Link href="/control/models">模型与计算</Link>{isAdmin&&<Link href="/control/system">系统状态</Link>}<span>{email}</span><form action={logout}><button className="secondary compact">退出登录</button></form></nav></header>;}

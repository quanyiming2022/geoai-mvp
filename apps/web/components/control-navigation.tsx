"use client";
import Link from 'next/link';
import {usePathname} from 'next/navigation';
export default function ControlNavigation({isAdmin}:{isAdmin:boolean}){const path=usePathname();return <nav className="control-nav" aria-label="控制中心区域">{[['/control/projects','项目'],['/control/rasters','影像数据'],['/control/models','模型与计算'],...(isAdmin?[['/control/system','系统状态']]:[])].map(([href,label])=><Link key={href} href={href} aria-current={(path===href||path.startsWith(href+'/'))?'page':undefined}>{label}</Link>)}</nav>;}

import {requireUser,api} from '../../lib/session';
import {logout} from '../actions';
import ControlNavigation from '../../components/control-navigation';
export default async function ControlLayout({children}:{children:React.ReactNode}){const user=await requireUser();const {is_admin}=await api<{is_admin:boolean}>('/admin/access');return <div className="control-shell"><header className="control-header"><strong>◈ GeoAI <span>Control Center</span></strong><ControlNavigation isAdmin={is_admin}/><span className="control-user">{user.email}</span><form action={logout}><button className="secondary compact">退出登录</button></form></header><main className="control-content">{children}</main></div>;}

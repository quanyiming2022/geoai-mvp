import Link from 'next/link';
import {api,requireUser} from '../../../../lib/session';
import LanguageSettings,{type LanguageConfiguration} from '../../../../components/language-settings';
export default async function LanguagePage(){await requireUser();const access=await api<{is_admin:boolean}>('/admin/access');if(!access.is_admin)return <p>语言模型配置仅向平台管理员开放。</p>;const config=await api<LanguageConfiguration>('/admin/llm');return <><p><Link href="/control/models">← 模型与计算</Link></p><LanguageSettings initial={config}/></>;}

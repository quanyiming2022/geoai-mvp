import {redirect,notFound} from 'next/navigation';
export default async function LegacyProject({params}:{params:Promise<{id:string}>}){const {id}=await params;if(!/^[0-9a-f-]{36}$/i.test(id))notFound();redirect(`/projects/${id}/settings`);}

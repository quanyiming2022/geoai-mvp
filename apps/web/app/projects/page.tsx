import {redirect} from 'next/navigation';
export default async function Projects({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){const q=await searchParams;const params=new URLSearchParams();for(const [key,value] of Object.entries(q))if(typeof value==='string')params.set(key,value);redirect('/control/projects'+(params.size?'?'+params:''));}

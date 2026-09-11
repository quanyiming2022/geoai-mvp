import {redirect} from 'next/navigation';
export default async function Models({searchParams}:{searchParams:Promise<Record<string,string>>}){redirect('/control/models?'+new URLSearchParams(await searchParams));}

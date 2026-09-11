"use server";
import {api,requireUser} from '../../../lib/session';
import {redirect} from 'next/navigation';
export async function recheckSystem(){await requireUser();const access=await api<{is_admin:boolean}>('/admin/access');if(!access.is_admin)throw new Error('Administrator required');const endpoints=await api<Array<{id:string;enabled:boolean}>>('/admin/model-endpoints');await Promise.allSettled(endpoints.filter(e=>e.enabled).map(e=>api('/admin/model-endpoints/'+e.id+'/test',{method:'POST'})));redirect('/control/system');}

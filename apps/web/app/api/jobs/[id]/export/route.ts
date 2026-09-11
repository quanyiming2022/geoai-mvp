import { NextResponse } from 'next/server';
import { api, ApiError } from '../../../../../lib/session';
export async function GET(_request:Request,{params}:{params:Promise<{id:string}>}) {
 const {id}=await params;
 if(!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({detail:'Invalid job'},{status:400});
 try { const data=await api(`/jobs/${id}/export`); return NextResponse.json(data,{headers:{'Content-Type':'application/geo+json','Content-Disposition':`attachment; filename="geoextract-${id}.geojson"`,'Cache-Control':'private, no-store'}}); }
 catch(error) { return NextResponse.json({detail:'Export unavailable'},{status:error instanceof ApiError ? error.status:503}); }
}

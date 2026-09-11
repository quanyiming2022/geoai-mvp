import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
export async function GET(_request: Request, { params }: { params: Promise<{ id: string; z: string; x: string; y: string }> }) {
 const {id,z,x,y} = await params;
 if (!/^[0-9a-f-]{36}$/i.test(id) || ![z,x,y].every(v => /^\d+$/.test(v))) return new NextResponse(null,{status:400});
 const token = (await cookies()).get('geoai-access')?.value;
 if (!token) return new NextResponse(null,{status:401});
 try {
   const response = await fetch(`${process.env.GEOAI_API_URL}/rasters/${id}/tiles/${z}/${x}/${y}.png`, {headers:{Authorization:`Bearer ${token}`}, cache:'no-store', signal:AbortSignal.timeout(30000)});
   return new NextResponse(response.body,{status:response.status,headers:{'Content-Type':response.headers.get('content-type') ?? 'image/png','Cache-Control':'private, no-store'}});
 } catch { return new NextResponse(null,{status:503}); }
}

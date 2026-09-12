import {NextRequest,NextResponse} from 'next/server';
import {api,ApiError} from '../../../../../../../../lib/session';
export async function POST(request:NextRequest,{params}:{params:Promise<{id:string;requestId:string}>}){
 const {id,requestId}=await params;let sameOrigin=false;try{sameOrigin=new URL(request.headers.get('origin')??'').host===request.headers.get('host');}catch{}
 if(!sameOrigin)return NextResponse.json({detail:'Origin rejected'},{status:403});
 if(![id,requestId].every(x=>/^[0-9a-f-]{36}$/i.test(x)))return NextResponse.json({detail:'Invalid request'},{status:400});
 try{return NextResponse.json(await api(`/projects/${id}/assistant/requests/${requestId}/cancel`,{method:'POST'}));}catch(error){return NextResponse.json({detail:'停止请求未确认'},{status:error instanceof ApiError?error.status:503});}
}

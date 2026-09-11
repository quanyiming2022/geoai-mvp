import { NextResponse } from 'next/server';
import { api, ApiError } from '../../../../../../lib/session';
export async function GET(_request: Request, { params }: { params: Promise<{ id: string; kind: string }> }) {
 const { id, kind } = await params;
 if (!/^[0-9a-f-]{36}$/i.test(id) || !['image','mask'].includes(kind)) return NextResponse.json({ detail: 'Invalid prompt' }, { status: 400 });
 try { const result = await api<{ url: string }>(`/prompts/${id}/${kind}/download`); return NextResponse.redirect(result.url, { status: 302, headers: { 'Cache-Control': 'private, no-store' } }); }
 catch (error) { return NextResponse.json({ detail: 'Download unavailable' }, { status: error instanceof ApiError ? error.status : 503 }); }
}

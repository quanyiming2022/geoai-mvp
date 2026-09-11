import { NextResponse } from 'next/server';
import { api, ApiError } from '../../../../../lib/session';
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ detail: 'Invalid asset' }, { status: 400 });
  try {
    const result = await api<{ url: string }>(`/rasters/${id}/download`);
    return NextResponse.redirect(result.url, { status: 302, headers: { 'Cache-Control': 'private, no-store' } });
  } catch (error) { return NextResponse.json({ detail: 'Download unavailable' }, { status: error instanceof ApiError ? error.status : 503 }); }
}

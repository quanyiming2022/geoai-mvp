import { cookies } from 'next/headers';
import { NextRequest, NextResponse } from 'next/server';
import { api, ApiError, saveSession, type Session } from '../../../../../lib/session';
import { needsRefresh } from '../../../../../lib/token-expiry.mjs';
export const runtime = 'nodejs';
export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const origin = request.headers.get('origin');
  let sameOrigin = false;
  try { sameOrigin = !!origin && new URL(origin).host === request.headers.get('host'); } catch {}
  if (!sameOrigin) return NextResponse.json({ detail: 'Origin rejected' }, { status: 403 });
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/i.test(id)) return NextResponse.json({ detail: 'Invalid project' }, { status: 400 });
  const jar = await cookies();
  let token = jar.get('geoai-access')?.value;
  const refresh = jar.get('geoai-refresh')?.value;
  if (needsRefresh(token) && refresh) {
    try {
      const session = await api<Session>('/auth/refresh', { method: 'POST', body: JSON.stringify({ refresh_token: refresh }) }, '');
      await saveSession(session); token = session.access_token;
    } catch (error) {
      return NextResponse.json({ detail: 'Session unavailable' }, { status: error instanceof ApiError ? error.status : 503 });
    }
  }
  if (!token) return NextResponse.json({ detail: 'Sign in required' }, { status: 401 });
  try {
    const headers: Record<string,string> = { Authorization: `Bearer ${token}`, 'Content-Type': 'image/tiff', 'x-filename': request.headers.get('x-filename') ?? '' };
    const length = request.headers.get('content-length'); if (length) headers['content-length'] = length;
    const init: RequestInit & { duplex: 'half' } = { method: 'POST', headers, body: request.body, duplex: 'half', cache: 'no-store', signal: request.signal };
    const response = await fetch(`${process.env.GEOAI_API_URL}/projects/${id}/rasters`, init);
    return new NextResponse(response.body, { status: response.status, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' } });
  } catch { return NextResponse.json({ detail: 'Upload service unavailable' }, { status: 503 }); }
}

import { NextRequest, NextResponse } from 'next/server';
import { needsRefresh } from './lib/token-expiry.mjs';

// Only refresh expiry here; protected services still verify identity on every request.
export async function proxy(request: NextRequest) {
  const access = request.cookies.get('geoai-access')?.value;
  const refresh = request.cookies.get('geoai-refresh')?.value;
  if (!needsRefresh(access) || !refresh) return NextResponse.next();
  let session;
  try {
    const result = await fetch(`${process.env.GEOAI_API_URL}/auth/refresh`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }), cache: 'no-store', signal: AbortSignal.timeout(15000)
    });
    if (!result.ok) {
      if (result.status !== 401) return new NextResponse('会话服务暂不可用，请稍后重试。', { status: 503 });
      const response = NextResponse.redirect(new URL('/login', request.url), 303);
      response.cookies.delete('geoai-access'); response.cookies.delete('geoai-refresh');
      return response;
    }
    session = await result.json();
  } catch { return new NextResponse('会话服务暂不可用，请稍后重试。', { status: 503 }); }
  request.cookies.set('geoai-access', session.access_token);
  request.cookies.set('geoai-refresh', session.refresh_token);
  const response = NextResponse.next({ request });
  const options = { httpOnly: true, sameSite: 'lax' as const, secure: process.env.GEOAI_COOKIE_SECURE === 'true', path: '/' };
  response.cookies.set('geoai-access', session.access_token, { ...options, maxAge: session.expires_in });
  response.cookies.set('geoai-refresh', session.refresh_token, { ...options, maxAge: 60 * 60 * 24 * 30 });
  response.headers.set('Cache-Control', 'private, no-store');
  return response;
}
export const config = { matcher: ['/projects/:path*', '/api/rasters/:path*'] };

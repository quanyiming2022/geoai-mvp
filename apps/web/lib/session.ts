import 'server-only';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

export const cookieOptions = { httpOnly: true, sameSite: 'lax' as const,
  secure: process.env.GEOAI_COOKIE_SECURE === 'true', path: '/' };
export type Session = { access_token: string; refresh_token: string; expires_in: number; confirmation_required?: boolean };
export type Project = { id: string; name: string; description: string; owner_id: string; created_at: string; my_role: string; members: Member[] };
export type Member = { user_id: string; role: string };
export class ApiError extends Error { constructor(public status: number) { super('Request failed'); } }
export async function api<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const access = token ?? (await cookies()).get('geoai-access')?.value;
  const response = await fetch(`${process.env.GEOAI_API_URL}${path}`, {
    ...init, cache: 'no-store', signal: AbortSignal.timeout(20000),
    headers: { 'Content-Type': 'application/json', ...(access ? { Authorization: `Bearer ${access}` } : {}), ...init.headers }
  });
  if (!response.ok) throw new ApiError(response.status);
  return response.status === 204 ? undefined as T : response.json();
}
export async function saveSession(session: Session) {
  const jar = await cookies();
  jar.set('geoai-access', session.access_token, { ...cookieOptions, maxAge: session.expires_in });
  jar.set('geoai-refresh', session.refresh_token, { ...cookieOptions, maxAge: 60 * 60 * 24 * 30 });
}
export async function requireUser() {
  try { return await api<{ id: string; email: string }>('/auth/me'); }
  catch (error) { if (error instanceof ApiError && error.status === 401) redirect('/login'); throw error; }
}

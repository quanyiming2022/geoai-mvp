export const dynamic = 'force-dynamic';
export async function GET() {
  const base = process.env.GEOAI_API_URL;
  if (!base) return Response.json({ status: 'unavailable', reason: 'API URL unconfigured' }, { status: 503 });
  try {
    const response = await fetch(new URL('/health/ready', base), { cache: 'no-store', signal: AbortSignal.timeout(15000) });
    return Response.json(await response.json(), { status: response.status });
  } catch {
    return Response.json({ status: 'unavailable', reason: 'API unreachable' }, { status: 503 });
  }
}

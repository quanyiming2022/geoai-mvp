"""Local AOI geometry, SQL RLS and role acceptance."""
import json
import time
import uuid
import httpx
from dotenv import dotenv_values
from migrate import ROOT, connection


def run():
    env = dotenv_values(ROOT / '.env')
    api = 'http://127.0.0.1:' + env['GEOAI_API_PORT']
    for _ in range(60):
        try:
            if httpx.get(api + '/health/ready', timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    key = env['SERVICE_ROLE_KEY']
    ids = []
    project_id = None
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'], headers={'apikey': key, 'Authorization': 'Bearer ' + key}, timeout=20) as admin:
        try:
            sessions = []
            for _ in range(2):
                seed = uuid.uuid4().hex
                credentials = {'email': seed + '@example.test', 'password': seed + 'Aa1!'}
                ids.append(admin.post('/auth/v1/admin/users', json={**credentials, 'email_confirm': True}).raise_for_status().json()['id'])
                sessions.append(httpx.post(api + '/auth/login', json=credentials, timeout=20).raise_for_status().json())
            headers = [{'Authorization': 'Bearer ' + s['access_token']} for s in sessions]
            with httpx.Client(base_url=api, timeout=20) as client:
                project_id = client.post('/projects', headers=headers[0], json={'name': 'P5 local acceptance'}).raise_for_status().json()['id']
                path = f'/projects/{project_id}/aois'
                geometry = {'type': 'Polygon', 'coordinates': [[[116.30,39.98],[116.31,39.98],[116.31,39.99],[116.30,39.98]]]}
                payload = {'name': 'Verified AOI', 'geometry': geometry}
                row = client.post(path, headers=headers[0], json=payload).raise_for_status().json()
                assert row['area_m2'] > 0 and row['geometry'] == geometry
                assert client.get(path, headers=headers[1]).status_code == 404
                assert client.post(path, headers=headers[1], json=payload).status_code == 404
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)", (json.dumps({'sub': ids[1], 'role': 'authenticated'}),))
                    assert conn.execute('SELECT id FROM public.aois WHERE id=%s', (row['id'],)).fetchall() == []
                client.post(f'/projects/{project_id}/members', headers=headers[0], json={'user_id': ids[1], 'role': 'viewer'}).raise_for_status()
                assert len(client.get(path, headers=headers[1]).raise_for_status().json()) == 1
                assert client.post(path, headers=headers[1], json=payload).status_code == 403
                client.patch(f'/projects/{project_id}/members/{ids[1]}', headers=headers[0], json={'role': 'editor'}).raise_for_status()
                assert client.post(path, headers=headers[1], json=payload).status_code == 201
                invalid = {'type': 'Polygon', 'coordinates': [[[0,0],[1,1],[1,0],[0,1],[0,0]]]}
                assert client.post(path, headers=headers[0], json={'name': 'crossed', 'geometry': invalid}).status_code == 422
                assert len(client.get(path, headers=headers[0]).raise_for_status().json()) == 2
                print('PASS: AOI polygon/area, invalid geometry, owner/editor write, viewer read-only, cross-user API and direct SQL RLS')
        finally:
            if project_id:
                with connection() as conn:
                    conn.execute('DELETE FROM public.projects WHERE id=%s', (project_id,))
            for uid in ids:
                admin.delete('/auth/v1/admin/users/' + uid).raise_for_status()


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL: ' + type(exc).__name__ + ' (secrets suppressed)')
        raise SystemExit(1) from None

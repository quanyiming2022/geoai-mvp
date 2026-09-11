"""Local endpoint CRUD, administrator isolation and actual worker connection test."""
import hashlib
import json
import time
import uuid
import httpx
from dotenv import dotenv_values
from migrate import ROOT,connection


def run():
    env=dotenv_values(ROOT/'.env')
    api='http://127.0.0.1:'+env['GEOAI_API_PORT']
    for _ in range(90):
        try:
            if httpx.get(api+'/health/ready',timeout=2).status_code==200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    key=env['SERVICE_ROLE_KEY']
    ids=[]
    release=None
    endpoint=None
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=20) as auth:
        try:
            tokens=[]
            for _ in range(2):
                seed=uuid.uuid4().hex
                credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
                uid=auth.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id']
                ids.append(uid)
                tokens.append(httpx.post(api+'/auth/login',json=credentials,timeout=20).raise_for_status().json()['access_token'])
            with connection() as conn:
                conn.execute('INSERT INTO geoai_internal.platform_admins(user_id) VALUES (%s)',(ids[0],))
            headers=[{'Authorization':'Bearer '+t} for t in tokens]
            with httpx.Client(base_url=api,timeout=20) as client:
                assert client.get('/admin/model-endpoints',headers=headers[1]).status_code==403
                release=client.post('/admin/models',headers=headers[0],json={'name':'P9 temporary transport fixture','model_name':'fake-real-rgb','model_version':'qa-'+uuid.uuid4().hex,'checkpoint_digest':hashlib.sha256(b'geoai-fake-real-rgb-v1').hexdigest(),'usage_policy':'internal_only'}).raise_for_status().json()
                # Worker has a fixed identity; use the exact version for identity validation.
                with connection() as conn:
                    conn.execute('UPDATE geoai_internal.model_releases SET model_version=%s WHERE id=%s',('1',release['id']))
                payload={'name':'Temporary local HTTP fixture','provider_type':'lan_http','base_url':'http://fake-real-worker:8001','model_release_id':release['id'],'enabled':True,'timeout_seconds':10}
                endpoint=client.post('/admin/model-endpoints',headers=headers[0],json=payload).raise_for_status().json()
                assert client.post('/admin/model-endpoints',headers=headers[1],json=payload).status_code==403
                assert client.post('/admin/model-endpoints',headers=headers[0],json={**payload,'base_url':'http://169.254.169.254'}).status_code==422
                assert client.post('/admin/models',headers=headers[0],json={'name':'bad','model_name':'SkySense++','model_version':'bad','usage_policy':'commercial'}).status_code==422
                test=client.post('/admin/model-endpoints/'+endpoint['id']+'/test',headers=headers[0]).raise_for_status().json()
                assert test['status']=='healthy' and test['model_info']['synthetic']
                before=client.get('/admin/model-endpoints',headers=headers[0]).raise_for_status().json()[0]
                client.put('/admin/models/'+release['id'],headers=headers[0],json={'name':'P9 temporary transport fixture','model_name':'fake-real-rgb','model_version':'2','checkpoint_digest':release['checkpoint_digest'],'usage_policy':'research_only'}).raise_for_status()
                changed=client.get('/admin/model-endpoints',headers=headers[0]).raise_for_status().json()[0]
                assert changed['health_status']=='offline' and changed['model_info'] is None
                assert changed['usage_policy']=='research_only' and changed['config_revision']>before['config_revision']
                with connection() as conn:
                    stale=conn.execute("UPDATE geoai_internal.model_endpoints SET health_status='healthy' WHERE id=%s AND config_revision=%s RETURNING id",(endpoint['id'],before['config_revision'])).fetchall()
                    assert stale==[]
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[1],'role':'authenticated'}),))
                    assert conn.execute('SELECT id FROM geoai_internal.model_endpoints WHERE id=%s',(endpoint['id'],)).fetchall()==[]
                client.put('/admin/model-endpoints/'+endpoint['id'],headers=headers[0],json={**payload,'enabled':False}).raise_for_status()
                disabled_test=client.post('/admin/model-endpoints/'+endpoint['id']+'/test',headers=headers[0]).raise_for_status().json()
                assert disabled_test['status']=='degraded'  # Mismatched release remains a failed identity check.
                disabled=client.get('/admin/model-endpoints',headers=headers[0]).raise_for_status().json()
                assert next(e for e in disabled if e['id']==endpoint['id'])['enabled'] is False
                assert all(e['id']!=endpoint['id'] for e in client.get('/models/available-endpoints',headers=headers[0]).raise_for_status().json())
                client.delete('/admin/model-endpoints/'+endpoint['id'],headers=headers[0]).raise_for_status()
                endpoint=None
                print('PASS: admin endpoint CRUD, real LAN HTTP health/model-info, disabled state, SSRF rejection, research policy and ordinary-user API/SQL denial')
        finally:
            with connection() as conn:
                if endpoint:
                    conn.execute('DELETE FROM geoai_internal.model_endpoints WHERE id=%s',(endpoint['id'],))
                if release:
                    conn.execute('DELETE FROM geoai_internal.model_releases WHERE id=%s',(release['id'],))
            for uid in ids:
                auth.delete('/auth/v1/admin/users/'+uid).raise_for_status()


if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL: '+type(exc).__name__+' (credentials suppressed)')
        raise SystemExit(1) from None

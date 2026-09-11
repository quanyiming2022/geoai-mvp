"""Real durable job lifecycle, idempotency, RLS and cancellation fence."""
import json
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import quote
import httpx
import psycopg
from pydantic import SecretStr
from dotenv import dotenv_values
from migrate import ROOT, connection
sys.path.insert(0,str(ROOT/'services/api'))
from geoai.job_worker import finish_job  # noqa: E402


def run():
    env=dotenv_values(ROOT/'.env')
    api='http://127.0.0.1:'+env['GEOAI_API_PORT']
    for _ in range(60):
        try:
            if httpx.get(api+'/health/ready',timeout=2).status_code==200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    compose=['sh',str(ROOT/'scripts/compose.sh')]
    cfg=SimpleNamespace(database_url=SecretStr('postgresql://postgres:'+quote(env['POSTGRES_PASSWORD'],safe='')+'@127.0.0.1:'+env['GEOAI_DB_PORT']+'/postgres'))
    key=env['SERVICE_ROLE_KEY']
    ids=[]
    project_id=None
    subprocess.run(compose+['stop','raster-worker'],check=True,stdout=subprocess.DEVNULL)
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=20) as admin:
        try:
            sessions=[]
            for _ in range(2):
                seed=uuid.uuid4().hex
                credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
                ids.append(admin.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id'])
                sessions.append(httpx.post(api+'/auth/login',json=credentials,timeout=20).raise_for_status().json())
            headers=[{'Authorization':'Bearer '+s['access_token']} for s in sessions]
            with httpx.Client(base_url=api,timeout=20) as client:
                project_id=client.post('/projects',headers=headers[0],json={'name':'P7 acceptance'}).raise_for_status().json()['id']
                path=f'/projects/{project_id}/jobs'
                payload={'kind':'diagnostic','idempotency_key':str(uuid.uuid4())}
                def create(_):
                    return client.post(path,headers=headers[0],json=payload).raise_for_status().json()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    duplicates=list(pool.map(create,range(2)))
                row=duplicates[0]
                assert row['id']==duplicates[1]['id']
                assert client.get('/jobs/'+row['id'],headers=headers[1]).status_code==404
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[1],'role':'authenticated'}),))
                    assert conn.execute('SELECT id FROM jobs WHERE id=%s',(row['id'],)).fetchall()==[]
                client.post(f'/projects/{project_id}/members',headers=headers[0],json={'user_id':ids[1],'role':'viewer'}).raise_for_status()
                assert client.get('/jobs/'+row['id'],headers=headers[1]).status_code==200
                assert client.post(path,headers=headers[1],json={**payload,'idempotency_key':str(uuid.uuid4())}).status_code==403
                assert client.post('/jobs/'+row['id']+'/cancel',headers=headers[1]).status_code in (403,409)
                token=uuid.uuid4()
                with connection() as conn:
                    conn.execute("UPDATE jobs SET status='running',claim_token=%s,started_at=now() WHERE id=%s",(token,row['id']))
                with connection() as locker:
                    locker.execute('SELECT id FROM jobs WHERE id=%s FOR UPDATE',(row['id'],))
                    began=time.monotonic()
                    locked=False
                    try:
                        finish_job(cfg,{'id':row['id'],'claim_token':token},{'blocked':True})
                    except psycopg.errors.LockNotAvailable:
                        locked=True
                    assert locked and time.monotonic()-began<8, 'Worker lock wait must be bounded'
                denied=False
                try:
                    with connection() as conn:
                        conn.execute('SET LOCAL ROLE authenticated')
                        conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[0],'role':'authenticated'}),))
                        conn.execute("UPDATE jobs SET status='queued' WHERE id=%s",(row['id'],))
                except psycopg.errors.InsufficientPrivilege:
                    denied=True
                assert denied, 'Database must reject running -> queued'
                assert client.post('/jobs/'+row['id']+'/cancel',headers=headers[0]).raise_for_status().json()['status']=='cancelled'
                assert not finish_job(cfg,{'id':row['id'],'claim_token':token},{'late':True})
                retry=client.post(path,headers=headers[0],json={**payload,'idempotency_key':str(uuid.uuid4())}).raise_for_status().json()
                with connection() as conn:
                    conn.execute("UPDATE jobs SET status='failed',error_code='qa_retry' WHERE id=%s",(retry['id'],))
                assert client.post('/jobs/'+retry['id']+'/retry',headers=headers[0]).raise_for_status().json()['status']=='queued'
                subprocess.run(compose+['restart','redis'],check=True,stdout=subprocess.DEVNULL)
                subprocess.run(compose+['start','raster-worker'],check=True,stdout=subprocess.DEVNULL)
                for _ in range(90):
                    result=client.get('/jobs/'+retry['id'],headers=headers[0]).raise_for_status().json()
                    if result['status'] in ('succeeded','failed'):
                        break
                    time.sleep(1)
                assert result['status']=='succeeded' and result['progress']==100 and result['result']['mock'] and result['result']['sample_count']==4
                assert client.get('/jobs/'+row['id'],headers=headers[0]).raise_for_status().json()['status']=='cancelled'
                print('PASS: concurrent idempotency, API/SQL RLS, viewer control denied, running cancellation fence, failed retry, Redis restart + worker recovery, MockComputeProvider completion')
        finally:
            subprocess.run(compose+['start','raster-worker'],check=True,stdout=subprocess.DEVNULL)
            if project_id:
                with connection() as conn:
                    conn.execute('DELETE FROM public.projects WHERE id=%s',(project_id,))
            for uid in ids:
                admin.delete('/auth/v1/admin/users/'+uid).raise_for_status()


if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL: '+type(exc).__name__+' (secrets suppressed)')
        raise SystemExit(1) from None

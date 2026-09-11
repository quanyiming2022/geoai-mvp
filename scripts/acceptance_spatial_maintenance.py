"""Local maintenance E2E, frozen running inputs, RLS, versioned masks and historical export."""
import subprocess
import json
import time
import uuid
import httpx
import numpy as np
import psycopg
from rasterio.io import MemoryFile
from dotenv import dotenv_values
from migrate import ROOT, connection
from make_fixture import make_fixture


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
    key=env['SERVICE_ROLE_KEY']
    ids=[]
    project_id=None
    objects=[]
    paused=False
    fixture=ROOT/'artifacts/p8-fixture.tif'
    fixture.parent.mkdir(exist_ok=True)
    make_fixture(fixture)
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=60) as admin:
        try:
            sessions=[]
            for _ in range(3):
                seed=uuid.uuid4().hex
                credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
                ids.append(admin.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id'])
                sessions.append(httpx.post(api+'/auth/login',json=credentials,timeout=20).raise_for_status().json())
            headers=[{'Authorization':'Bearer '+s['access_token']} for s in sessions]
            with httpx.Client(base_url=api,timeout=60) as client:
                project_id=client.post('/projects',headers=headers[0],json={'name':'P8 full E2E'}).raise_for_status().json()['id']
                asset=client.post(f'/projects/{project_id}/rasters',headers={**headers[0],'X-Filename':'p6.tif'},content=fixture.read_bytes()).raise_for_status().json()
                for _ in range(170):
                    asset=client.get(f'/projects/{project_id}/rasters',headers=headers[0]).raise_for_status().json()[0]
                    if asset['status'] in ('ready','failed'):
                        break
                    time.sleep(2)
                assert asset['status']=='ready'
                objects.extend([asset['object_key'],asset['cog_object_key'],asset['thumbnail_object_key']])
                geometry={'type':'Polygon','coordinates':[[[116.305,39.985],[116.315,39.985],[116.305,39.995],[116.305,39.985]]]}
                payload={'name':'Local support','class_label':'vegetation','description':'metadata only','raster_asset_id':asset['id'],'geometry':geometry}
                path=f'/projects/{project_id}/prompts'
                prompt=client.post(path,headers=headers[0],json=payload).raise_for_status().json()
                objects.extend([prompt['support_image_object'],prompt['support_mask_object']])
                assert prompt['source_crs']=='EPSG:4326' and prompt['geometry']==geometry
                web='http://127.0.0.1:'+env['GEOAI_WEB_PORT']
                forwarded=httpx.get(web+f"/api/prompts/{prompt['id']}/mask/download",cookies={'geoai-access':sessions[0]['access_token']},timeout=20)
                assert forwarded.status_code==302 and 'token=' in forwarded.headers['location']
                blobs=[]
                for kind in ('image','mask'):
                    link=client.get(f"/prompts/{prompt['id']}/{kind}/download",headers=headers[0]).raise_for_status().json()['url']
                    blobs.append(httpx.get(link,timeout=20).raise_for_status().content)
                    assert client.get(f"/prompts/{prompt['id']}/{kind}/download",headers=headers[1]).status_code==404
                with MemoryFile(blobs[0]) as im, MemoryFile(blobs[1]) as mm,im.open() as a,mm.open() as b:
                    assert a.crs==b.crs and a.transform==b.transform and a.shape==b.shape
                    assert set(np.unique(b.read(1)))=={0,1} and max(a.shape)<=512
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[1],'role':'authenticated'}),))
                    assert conn.execute('SELECT id FROM visual_prompts WHERE id=%s',(prompt['id'],)).fetchall()==[]
                client.post(f'/projects/{project_id}/members',headers=headers[0],json={'user_id':ids[1],'role':'viewer'}).raise_for_status()
                assert len(client.get(path,headers=headers[1]).raise_for_status().json())==1
                assert client.post(path,headers=headers[1],json=payload).status_code==403
                outside={**payload,'geometry':{'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,0]]]}}
                assert client.post(path,headers=headers[0],json=outside).status_code==422
                aoi=client.post(f'/projects/{project_id}/aois',headers=headers[0],json={'name':'E2E AOI','geometry':geometry}).raise_for_status().json()
                # Stop only this local worker after raster preparation; always unpause in finally.
                subprocess.run(['docker','pause','geoai-mvp-raster-worker-1'],check=True,capture_output=True)
                paused=True
                request={'kind':'geoextract','idempotency_key':str(uuid.uuid4()),'raster_asset_id':asset['id'],'prompt_id':prompt['id'],'aoi_id':aoi['id']}
                job=client.post(f'/projects/{project_id}/jobs',headers=headers[0],json=request).raise_for_status().json()
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[1],json={**request,'idempotency_key':str(uuid.uuid4())}).status_code==403
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[0],json={**request,'prompt_id':str(uuid.uuid4())}).status_code==422
                with connection() as conn:
                    frozen=conn.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(job['id'],)).fetchone()[0]
                    conn.execute("UPDATE jobs SET status='running',claim_token=%s,started_at=now() WHERE id=%s",(uuid.uuid4(),job['id']))
                edit_geometry={'type':'Polygon','coordinates':[[[116.306,39.986],[116.314,39.986],[116.306,39.994],[116.306,39.986]]]}
                aoi_path=f"/projects/{project_id}/aois/{aoi['id']}"
                prompt_path=f"/projects/{project_id}/prompts/{prompt['id']}"
                aoi_edit={'name':'AOI edited','description':'Updated boundary','geometry':edit_geometry,'expected_revision':aoi['revision']}
                prompt_edit={**payload,'name':'Prompt edited','class_label':'building','description':'Updated description','geometry':edit_geometry,'expected_revision':prompt['revision']}
                for path_,body in [(aoi_path,aoi_edit),(prompt_path,prompt_edit)]:
                    assert client.put(path_,headers=headers[1],json=body).status_code==403
                    assert client.request('DELETE',path_,headers=headers[1],json={'expected_revision':1}).status_code==403
                # Direct SQL RLS must independently reject viewer writes.
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[1],'role':'authenticated'}),))
                    assert conn.execute('UPDATE aois SET deleted_at=now() WHERE id=%s RETURNING id',(aoi['id'],)).fetchall()==[]
                    assert conn.execute("UPDATE visual_prompts SET class_label='forbidden' WHERE id=%s RETURNING id",(prompt['id'],)).fetchall()==[]
                # Existing project role implementation; do not invent an admin role.
                client.patch(f'/projects/{project_id}/members/{ids[1]}',headers=headers[0],json={'role':'editor'}).raise_for_status()
                aoi_new=client.put(aoi_path,headers=headers[1],json=aoi_edit).raise_for_status().json()
                prompt_new=client.put(prompt_path,headers=headers[1],json=prompt_edit).raise_for_status().json()
                objects.extend([prompt_new['support_image_object'],prompt_new['support_mask_object']])
                assert prompt_new['class_label']=='building' and prompt_new['description']=='Updated description'
                assert prompt_new['artifact_version'] and prompt_new['support_mask_object']!=prompt['support_mask_object']
                assert client.put(prompt_path,headers=headers[1],json=prompt_edit).status_code==409
                new_blobs=[]
                for kind in ('image','mask'):
                    link=client.get(f"/prompts/{prompt['id']}/{kind}/download",headers=headers[0]).raise_for_status().json()['url']
                    new_blobs.append(httpx.get(link,timeout=20).raise_for_status().content)
                assert new_blobs[1]!=blobs[1]
                with MemoryFile(new_blobs[0]) as im,MemoryFile(new_blobs[1]) as mm,im.open() as si,mm.open() as sm:
                    assert si.shape==sm.shape and si.transform==sm.transform and set(np.unique(sm.read(1)))=={0,1}
                # Invalid geometry/crop cannot publish any DB update.
                invalid={**prompt_edit,'expected_revision':prompt_new['revision'],'geometry':outside['geometry']}
                assert client.put(prompt_path,headers=headers[1],json=invalid).status_code==422
                assert client.get(f'/projects/{project_id}/prompts',headers=headers[0]).json()[0]['revision']==prompt_new['revision']
                client.request('DELETE',aoi_path,headers=headers[1],json={'expected_revision':aoi_new['revision']}).raise_for_status()
                client.request('DELETE',prompt_path,headers=headers[1],json={'expected_revision':prompt_new['revision']}).raise_for_status()
                assert client.get(f'/projects/{project_id}/aois',headers=headers[0]).json()==[]
                assert client.get(f'/projects/{project_id}/prompts',headers=headers[0]).json()==[]
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[0],json=request).raise_for_status().json()['id']==job['id']
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[0],json={**request,'idempotency_key':str(uuid.uuid4())}).status_code==422
                with connection() as conn:
                    assert conn.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(job['id'],)).fetchone()[0]==frozen
                # Execute the isolated running claim after both resources changed/deleted.
                code="from geoai.config import Settings; from geoai.raster_worker import database; from geoai.job_worker import execute_job; c=database(Settings()); row=c.execute('SELECT * FROM jobs WHERE id=%s',('"+job['id']+"',)).fetchone(); c.close(); execute_job(row)"
                subprocess.run(['docker','exec','geoai-mvp-api-1','python','-c',code],check=True,capture_output=True)
                subprocess.run(['docker','unpause','geoai-mvp-raster-worker-1'],check=True,capture_output=True)
                paused=False
                client.patch(f'/projects/{project_id}/members/{ids[1]}',headers=headers[0],json={'role':'viewer'}).raise_for_status()
                for _ in range(100):
                    job=client.get('/jobs/'+job['id'],headers=headers[0]).raise_for_status().json()
                    if job['status'] in ('succeeded','failed'):
                        break
                    time.sleep(1)
                assert job['status']=='succeeded' and job['result']['mock'] and job['result']['result_count']>0
                results=client.get(f'/projects/{project_id}/results',headers=headers[0]).raise_for_status().json()
                assert results and all(r['job_id']==job['id'] and r['area_m2']>0 and r['source_metadata']['model_release']=='mock-v1' for r in results)
                result=results[0]
                assert client.get('/jobs/'+job['id']+'/export',headers=headers[2]).status_code==404
                assert client.post('/results/'+result['id']+'/review',headers=headers[2],json={'action':'accepted'}).status_code==404
                assert client.post('/results/'+result['id']+'/review',headers=headers[1],json={'action':'accepted'}).status_code==403
                with connection() as conn:
                    conn.execute('SET LOCAL ROLE authenticated')
                    conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[2],'role':'authenticated'}),))
                    assert conn.execute('SELECT id FROM extraction_results WHERE id=%s',(result['id'],)).fetchall()==[]
                protected=False
                try:
                    with connection() as conn:
                        conn.execute('SET LOCAL ROLE authenticated')
                        conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[0],'role':'authenticated'}),))
                        conn.execute('UPDATE extraction_results SET geometry=geometry WHERE id=%s',(result['id'],))
                except psycopg.errors.InsufficientPrivilege:
                    protected=True
                assert protected
                client.post('/results/'+result['id']+'/review',headers=headers[0],json={'action':'rejected'}).raise_for_status()
                assert client.get('/jobs/'+job['id']+'/export',headers=headers[0]).raise_for_status().json()['features']==[]
                accepted=client.post('/results/'+result['id']+'/review',headers=headers[0],json={'action':'accepted'}).raise_for_status().json()
                assert accepted['geometry']==result['geometry']
                export=httpx.get(web+'/api/jobs/'+job['id']+'/export',cookies={'geoai-access':sessions[0]['access_token']},timeout=20).raise_for_status()
                assert 'application/geo+json' in export.headers['content-type'] and 'attachment' in export.headers['content-disposition']
                collection=export.json()
                assert collection['type']=='FeatureCollection' and len(collection['features'])==1 and collection['metadata']['crs']=='EPSG:4326'
                assert collection['features'][0]['properties']['source_metadata']['source_raster']==asset['id']
                with connection() as conn:
                    audit=conn.execute('SELECT action,reviewer FROM review_actions WHERE result_id=%s ORDER BY created_at',(result['id'],)).fetchall()
                    assert [a[0] for a in audit]==['rejected','accepted'] and all(str(a[1])==ids[0] for a in audit)
                    assert conn.execute('SELECT extensions.ST_IsValid(geometry),extensions.ST_SRID(geometry) FROM extraction_results WHERE id=%s',(result['id'],)).fetchone()==(True,4326)
                fresh_prompt=client.post(f'/projects/{project_id}/prompts',headers=headers[0],json=payload).raise_for_status().json()
                objects.extend([fresh_prompt['support_image_object'],fresh_prompt['support_mask_object']])
                fresh_aoi=client.post(f'/projects/{project_id}/aois',headers=headers[0],json={'name':'Fresh AOI','geometry':geometry}).raise_for_status().json()
                request={**request,'prompt_id':fresh_prompt['id'],'aoi_id':fresh_aoi['id']}
                newer=client.post(f'/projects/{project_id}/jobs',headers=headers[0],json={**request,'idempotency_key':str(uuid.uuid4())}).raise_for_status().json()
                for _ in range(100):
                    newer=client.get('/jobs/'+newer['id'],headers=headers[0]).raise_for_status().json()
                    if newer['status'] in ('succeeded','failed'):
                        break
                    time.sleep(1)
                assert newer['status']=='succeeded'
                latest=client.get(f'/projects/{project_id}/results',headers=headers[0]).raise_for_status().json()
                older=client.get(f'/projects/{project_id}/results',params={'job_id':job['id']},headers=headers[0]).raise_for_status().json()
                assert all(r['job_id']==newer['id'] for r in latest) and any(r['id']==result['id'] and r['review_status']=='accepted' for r in older)
                page=client.get(f'/projects/{project_id}/jobs?offset=1',headers=headers[0]).raise_for_status().json()
                assert page[0]['id']==job['id']
                print('PASS: historical job results and job pagination')
                print('PASS: maintenance CRUD/versioned crop/running snapshot/deletion history plus login/project/upload/COG/prompt/AOI/job/MockAdapter/polygon/reject/accept/Next GeoJSON export; SQL RLS, original prediction immutable and audit history verified')
        finally:
            if paused:subprocess.run(['docker','unpause','geoai-mvp-raster-worker-1'],check=False,capture_output=True)
            for obj in objects:
                admin.request('DELETE','/storage/v1/object/'+env['STORAGE_BUCKET'],json={'prefixes':[obj]}).raise_for_status()
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

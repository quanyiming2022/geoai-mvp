"""Complete local Mock GeoExtract flow, audit, export and project isolation."""
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
    second_project=None
    objects=[]
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
                request={'kind':'geoextract','idempotency_key':str(uuid.uuid4()),'raster_asset_id':asset['id'],'prompt_id':prompt['id'],'aoi_id':aoi['id']}
                job=client.post(f'/projects/{project_id}/jobs',headers=headers[0],json=request).raise_for_status().json()
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[1],json={**request,'idempotency_key':str(uuid.uuid4())}).status_code==403
                assert client.post(f'/projects/{project_id}/jobs',headers=headers[0],json={**request,'prompt_id':str(uuid.uuid4())}).status_code==422
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
                second_project=client.post('/projects',headers=headers[0],json={'name':'Shared raster Project B'}).raise_for_status().json()['id']
                link=f'/projects/{second_project}/rasters/{asset["id"]}/link'
                client.post(link,headers=headers[0]).raise_for_status()
                shared=client.get(f'/projects/{second_project}/rasters',headers=headers[0]).raise_for_status().json()[0]
                assert shared['cog_object_key']==asset['cog_object_key'] and shared['storage_project_id']==project_id
                shared_prompt=client.post(f'/projects/{second_project}/prompts',headers=headers[0],json=payload).raise_for_status().json()
                objects.extend([shared_prompt['support_image_object'],shared_prompt['support_mask_object']])
                shared_aoi=client.post(f'/projects/{second_project}/aois',headers=headers[0],json={'name':'Project B AOI','geometry':geometry}).raise_for_status().json()
                shared_job=client.post(f'/projects/{second_project}/jobs',headers=headers[0],json={**request,'prompt_id':shared_prompt['id'],'aoi_id':shared_aoi['id'],'idempotency_key':str(uuid.uuid4())}).raise_for_status().json()
                for _ in range(100):
                    shared_job=client.get('/jobs/'+shared_job['id'],headers=headers[0]).raise_for_status().json()
                    if shared_job['status'] in ('succeeded','failed'):break
                    time.sleep(1)
                assert shared_job['status']=='succeeded',shared_job.get('error_code')
                assert not any(p['id']==prompt['id'] for p in client.get(f'/projects/{second_project}/prompts',headers=headers[0]).json())
                client.post(f'/projects/{second_project}/members',headers=headers[0],json={'user_id':ids[1],'role':'editor'}).raise_for_status()
                client.patch(f'/projects/{second_project}/rasters/{asset["id"]}',headers=headers[1],json={'name':'Editor alias'}).raise_for_status()
                assert client.request('DELETE',f'/raster-assets/{asset["id"]}',headers=headers[1],json={'confirmed':True}).status_code==403
                client.patch(f'/projects/{second_project}/rasters/{asset["id"]}',headers=headers[0],json={'name':'项目 B 别名'}).raise_for_status()
                assert client.get(f'/projects/{project_id}/rasters',headers=headers[0]).json()[0]['filename']==asset['filename']
                duplicate=client.post(f'/projects/{second_project}/rasters',headers={**headers[0],'X-Filename':'same.tif'},content=fixture.read_bytes())
                assert duplicate.status_code==409 and duplicate.json()['detail']['code']=='RASTER_EXISTS'
                assert client.request('DELETE',f'/raster-assets/{asset["id"]}',headers=headers[0],json={'confirmed':True}).status_code==409
                assert client.patch(f'/projects/{project_id}/rasters/{asset["id"]}',headers=headers[1],json={'name':'forbidden'}).status_code==403
                assert client.request('DELETE',f'/projects/{project_id}/rasters/{asset["id"]}/link',headers=headers[1],json={'confirmed':True}).status_code==403
                revision=accepted['revision']
                changes={'expected_revision':revision,'result_name':'建筑提取结果-01','description':'成果维护验收'}
                assert client.patch('/results/'+result['id'],headers=headers[1],json=changes).status_code==403
                renamed=client.patch('/results/'+result['id'],headers=headers[0],json=changes).raise_for_status().json()
                assert renamed['result_name']=='建筑提取结果-01' and renamed['description']=='成果维护验收'
                assert client.patch('/results/'+result['id'],headers=headers[0],json=changes).status_code==409
                ring=result['geometry']['coordinates'][0];cx=sum(p[0] for p in ring[:-1])/len(ring[:-1]);cy=sum(p[1] for p in ring[:-1])/len(ring[:-1])
                edited_geom={'type':'Polygon','coordinates':[[[cx+(p[0]-cx)*0.8,cy+(p[1]-cy)*0.8] for p in ring]]}
                edited=client.patch('/results/'+result['id'],headers=headers[0],json={'expected_revision':renamed['revision'],'geometry':edited_geom}).raise_for_status().json()
                exported=client.get('/results/'+result['id']+'/export',headers=headers[0]).raise_for_status().json()
                assert exported['features'][0]['geometry']==edited['geometry'] and edited['area_m2']<result['area_m2']
                webexport=httpx.get(web+'/api/results/'+result['id']+'/export',cookies={'geoai-access':sessions[0]['access_token']},timeout=20).raise_for_status()
                assert 'filename*=UTF-8' in webexport.headers['content-disposition']
                delete={'expected_revision':edited['revision'],'confirmed':True}
                assert client.request('DELETE','/results/'+result['id'],headers=headers[1],json=delete).status_code==403
                client.request('DELETE','/results/'+result['id'],headers=headers[0],json=delete).raise_for_status()
                assert not any(r['id']==result['id'] for r in client.get(f'/projects/{project_id}/results',params={'job_id':job['id']},headers=headers[0]).json())
                assert client.get('/jobs/'+job['id'],headers=headers[0]).json()['result']['result_count']>0
                revisions=client.get('/results/'+result['id']+'/revisions',headers=headers[0]).raise_for_status().json()
                assert [r['operation'] for r in revisions][-3:]==['metadata','geometry','delete']
                with connection() as conn:
                    assert conn.execute('SELECT extensions.ST_AsGeoJSON(geometry)::json FROM extraction_results WHERE id=%s',(result['id'],)).fetchone()[0]==result['geometry']
                client.request('DELETE',f'/projects/{project_id}/rasters/{asset["id"]}/link',headers=headers[0],json={'confirmed':True}).raise_for_status()
                assert len(client.get(f'/projects/{second_project}/rasters',headers=headers[0]).json())==1
                assert client.get('/jobs/'+job['id']+'/export',headers=headers[0]).status_code==200
                client.request('DELETE',link,headers=headers[0],json={'confirmed':True}).raise_for_status()
                client.request('DELETE',f'/raster-assets/{asset["id"]}',headers=headers[0],json={'confirmed':True}).raise_for_status()
                assert not any(r['id']==asset['id'] for r in client.get('/raster-assets',headers=headers[0]).json())
                assert client.get('/jobs/'+job['id'],headers=headers[0]).status_code==200
                print('PASS: asset reuse/dedup/alias/unlink/soft deletion; result rename/geometry/export/revisions/soft deletion; viewer denial and immutable history')
                print('PASS: historical job results and job pagination')
                print('PASS: P8 login/project/upload/COG/prompt/AOI/job/MockAdapter/polygon/reject/accept/Next GeoJSON export; SQL RLS, original prediction immutable and audit history verified')
        finally:
            for obj in objects:
                admin.request('DELETE','/storage/v1/object/'+env['STORAGE_BUCKET'],json={'prefixes':[obj]}).raise_for_status()
            if second_project:
                with connection() as conn:conn.execute('DELETE FROM public.projects WHERE id=%s',(second_project,))
            if project_id:
                with connection() as conn:
                    conn.execute('DELETE FROM public.projects WHERE id=%s',(project_id,))
                    conn.execute('DELETE FROM public.raster_assets WHERE project_id=%s',(project_id,))
            for uid in ids:
                admin.delete('/auth/v1/admin/users/'+uid).raise_for_status()


if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL: '+type(exc).__name__+' (secrets suppressed)')
        raise SystemExit(1) from None

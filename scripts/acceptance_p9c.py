"""P9C real local LLM -> confirmed existing Mock job, plus unchanged P8 assertions."""
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
            with httpx.Client(base_url=api,timeout=185) as client:
                project_id=client.post('/projects',headers=headers[0],json={'name':'P9C temporary LLM acceptance'}).raise_for_status().json()['id']
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
                # Name-only updates must preserve all spatial/provenance fields.
                for collection,item,table in [('aois',aoi,'aois'),('prompts',prompt,'visual_prompts')]:
                    endpoint=f'/projects/{project_id}/{collection}/{item["id"]}'
                    change={'name':'重命名验证','expected_name':item['name']}
                    assert client.patch(endpoint,headers=headers[1],json=change).status_code==403
                    assert client.patch(endpoint,headers=headers[2],json=change).status_code==404
                    assert client.patch(endpoint,headers=headers[0],json={**change,'geometry':geometry}).status_code==422
                    client.patch(endpoint,headers=headers[0],json=change).raise_for_status()
                    assert client.patch(endpoint,headers=headers[0],json=change).status_code==409
                    client.patch(endpoint,headers=headers[0],json={'name':item['name'],'expected_name':'重命名验证'}).raise_for_status()
                    restored=next(x for x in client.get(f'/projects/{project_id}/{collection}',headers=headers[0]).raise_for_status().json() if x['id']==item['id'])
                    assert {k:v for k,v in restored.items() if k not in ('revision','updated_at','updated_by')}=={k:v for k,v in item.items() if k not in ('revision','updated_at','updated_by')}
                    assert restored['revision']==item['revision']+2
                    description_change={'name':item['name'],'expected_name':item['name'],'description':'用途与目标说明','expected_description':item.get('description','')}
                    assert client.patch(endpoint,headers=headers[1],json=description_change).status_code==403
                    assert client.patch(endpoint,headers=headers[2],json=description_change).status_code==404
                    client.patch(endpoint,headers=headers[0],json=description_change).raise_for_status()
                    assert client.patch(endpoint,headers=headers[0],json=description_change).status_code==409
                    client.patch(endpoint,headers=headers[0],json={**description_change,'description':item.get('description',''),'expected_description':'用途与目标说明'}).raise_for_status()
                    final=next(x for x in client.get(f'/projects/{project_id}/{collection}',headers=headers[0]).raise_for_status().json() if x['id']==item['id'])
                    assert {k:v for k,v in final.items() if k not in ('revision','updated_at','updated_by')}=={k:v for k,v in item.items() if k not in ('revision','updated_at','updated_by')}
                    assert final['revision']==item['revision']+4
                    with connection() as conn:
                        assert conn.execute("SELECT has_column_privilege('authenticated',%s,'name','UPDATE'),has_column_privilege('authenticated',%s,'geometry','UPDATE')",('public.'+table,'public.'+table)).fetchone()==(True,True)
                        conn.execute('SET LOCAL ROLE authenticated')
                        conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':ids[1],'role':'authenticated'}),))
                        assert conn.execute(f"UPDATE public.{table} SET name='denied' WHERE id=%s RETURNING id",(item['id'],)).fetchall()==[]
                client.patch(f'/projects/{project_id}/members/{ids[1]}',headers=headers[0],json={'role':'editor'}).raise_for_status()
                client.patch(f'/projects/{project_id}/aois/{aoi["id"]}',headers=headers[1],json={'name':'编辑者改名','expected_name':aoi['name']}).raise_for_status()
                client.patch(f'/projects/{project_id}/aois/{aoi["id"]}',headers=headers[1],json={'name':aoi['name'],'expected_name':'编辑者改名'}).raise_for_status()
                client.patch(f'/projects/{project_id}/members/{ids[1]}',headers=headers[0],json={'role':'viewer'}).raise_for_status()
                print('PASS: AOI/prompt rename, conflict, immutable spatial data, editor/viewer/outsider and column permissions')
                request={'kind':'geoextract','idempotency_key':str(uuid.uuid4()),'raster_asset_id':asset['id'],'prompt_id':prompt['id'],'aoi_id':aoi['id']}
                assert client.get('/admin/llm',headers=headers[0]).status_code==403
                assert client.put('/admin/llm',headers=headers[0],json={}).status_code in (403,422)
                planned=client.post(f'/projects/{project_id}/assistant/plan',headers=headers[0],json={'text':'请使用 p6.tif 影像、Local support 视觉样例和 E2E AOI 搜索范围，生成 Mock 提取测试任务草案。明确使用 Mock，不使用真实 Worker。'}).raise_for_status().json()
                assert planned['kind']=='draft',planned
                assert client.get(f'/projects/{project_id}/jobs',headers=headers[0]).raise_for_status().json()==[]
                confirmation={'draft_id':planned['draft_id'],'confirmed':True}
                assert client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[1],json=confirmation).status_code==403
                assert client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[2],json=confirmation).status_code==404
                assert client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[0],json={**confirmation,'confirmed':False}).status_code==422
                assert client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[0],json={**confirmation,'model_url':'http://localhost'}).status_code==422
                job=client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[0],json=confirmation).raise_for_status().json()
                assert client.post(f'/projects/{project_id}/assistant/confirm',headers=headers[0],json=confirmation).raise_for_status().json()['id']==job['id']
                assert job['kind']=='geoextract' and job['raster_asset_id']==asset['id'] and job['prompt_id']==prompt['id'] and job['aoi_id']==aoi['id']
                (ROOT/'artifacts/p9c-llm-acceptance.json').write_text(json.dumps({key:planned[key] for key in ('llm_model','llm_mode','runtime_ms','labels')},ensure_ascii=False,indent=2))
                print('PASS: real local LLM draft; no job before confirmation; owner-bound draft; viewer/outsider blocked; idempotent confirmation')
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
                print('PASS: historical job results and job pagination')
                print('PASS: P8 login/project/upload/COG/prompt/AOI/job/MockAdapter/polygon/reject/accept/Next GeoJSON export; SQL RLS, original prediction immutable and audit history verified')
        finally:
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

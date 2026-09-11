"""Real local raster -> visual prompt -> georeferenced image/mask acceptance."""
import json
import time
import uuid
import httpx
import numpy as np
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
    fixture=ROOT/'artifacts/p6-fixture.tif'
    fixture.parent.mkdir(exist_ok=True)
    make_fixture(fixture)
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=60) as admin:
        try:
            sessions=[]
            for _ in range(2):
                seed=uuid.uuid4().hex
                credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
                ids.append(admin.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id'])
                sessions.append(httpx.post(api+'/auth/login',json=credentials,timeout=20).raise_for_status().json())
            headers=[{'Authorization':'Bearer '+s['access_token']} for s in sessions]
            with httpx.Client(base_url=api,timeout=60) as client:
                project_id=client.post('/projects',headers=headers[0],json={'name':'P6 acceptance'}).raise_for_status().json()['id']
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
                print('PASS: real prompt crop, binary mask/grid/CRS, private artifacts, owner create, viewer read-only, outsider SQL/API denial, outside geometry rejected')
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

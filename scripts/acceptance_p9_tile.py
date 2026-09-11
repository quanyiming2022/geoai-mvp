"""Local synthetic HTTP -> source-resolution tile -> PostGIS/review/export acceptance."""
import hashlib
import json
import time
import uuid
import httpx
import numpy as np
import rasterio
from rasterio.transform import from_origin
from dotenv import dotenv_values
from migrate import ROOT,connection


def run():
    env=dotenv_values(ROOT/'.env')
    api='http://127.0.0.1:'+env['GEOAI_API_PORT']
    fixture=ROOT/'artifacts/p9-native-1024.tif'
    fixture.parent.mkdir(exist_ok=True)
    yy,xx=np.indices((1024,1024))
    pixels=np.stack([xx%256,yy%256,(xx+yy)%256]).astype('uint8')
    with rasterio.open(fixture,'w',driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=from_origin(116,40,.00001,.00001)) as ds:
        ds.write(pixels)
    uid=project=endpoint=release=None
    objects=[]
    key=env['SERVICE_ROLE_KEY']
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=60) as auth:
        try:
            seed=uuid.uuid4().hex
            credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
            uid=auth.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id']
            token=httpx.post(api+'/auth/login',json=credentials,timeout=20).raise_for_status().json()['access_token']
            # Register temporary fixture infrastructure; never grant a test user administrator access.
            with connection() as conn:
                release=str(conn.execute("INSERT INTO geoai_internal.model_releases(name,model_name,model_version,checkpoint_digest,usage_policy) VALUES (%s,'fake-real-rgb','1',%s,'internal_only') RETURNING id",('P9 fixture '+seed,hashlib.sha256(b'geoai-fake-real-rgb-v1').hexdigest())).fetchone()[0])
                endpoint=str(conn.execute("INSERT INTO geoai_internal.model_endpoints(name,provider_type,base_url,enabled,usage_policy,model_release_id) VALUES ('P9 fixture','lan_http','http://fake-real-worker:8001',true,'internal_only',%s) RETURNING id",(release,)).fetchone()[0])
            with httpx.Client(base_url=api,headers={'Authorization':'Bearer '+token},timeout=60) as client:
                catalog=client.get('/models/available-endpoints').raise_for_status().json()
                selected=next(e for e in catalog if e['id']==endpoint)
                assert not any(k in selected for k in ('base_url','secret_ref','auth_type'))
                assert client.get('/admin/model-endpoints').status_code==403
                project=client.post('/projects',json={'name':'P9 temporary native-tile acceptance'}).raise_for_status().json()['id']
                assets=[]
                for name in ('support.tif','different-query.tif'):
                    asset=client.post(f'/projects/{project}/rasters',headers={'X-Filename':name},content=fixture.read_bytes()).raise_for_status().json()
                    for _ in range(180):
                        asset=next(r for r in client.get(f'/projects/{project}/rasters').raise_for_status().json() if r['id']==asset['id'])
                        if asset['status'] in ('ready','failed'):
                            break
                        time.sleep(1)
                    assert asset['status']=='ready',asset.get('error_code')
                    assets.append(asset)
                    objects.extend([asset['object_key'],asset['cog_object_key'],asset['thumbnail_object_key']])
                geometry={'type':'Polygon','coordinates':[[[116.001,39.999],[116.002,39.999],[116.002,39.998],[116.001,39.998],[116.001,39.999]]]}
                preview=client.post(f'/projects/{project}/prompts/preview',json={'name':'Preview','raster_asset_id':assets[0]['id'],'geometry':geometry}).raise_for_status().json()
                import base64
                assert all(base64.b64decode(preview[k].split(',',1)[1]).startswith(b'\x89PNG') for k in ('image','mask'))
                prompt=client.post(f'/projects/{project}/prompts',json={'name':'Reusable target','raster_asset_id':assets[0]['id'],'geometry':geometry}).raise_for_status().json()
                objects.extend([prompt['support_image_object'],prompt['support_mask_object']])
                payload={'kind':'geoextract_tile','idempotency_key':str(uuid.uuid4()),'raster_asset_id':assets[1]['id'],'prompt_id':prompt['id'],'model_endpoint_id':endpoint,'model_release_id':release,'endpoint_revision':selected['config_revision'],'query_col':201,'query_row':307,'seed':57}
                path=f'/projects/{project}/jobs'
                assert client.post(path,json={**payload,'model_url':'http://127.0.0.1'}).status_code==422
                assert client.post(path,json={**payload,'query_col':800}).status_code==422
                job=client.post(path,json=payload).raise_for_status().json()
                repeated=client.post(path,json=payload).raise_for_status().json()
                assert repeated['id']==job['id']
                assert client.post(path,json={**payload,'seed':58}).status_code==409
                for _ in range(150):
                    job=client.get('/jobs/'+job['id']).raise_for_status().json()
                    if job['status'] in ('succeeded','failed'):
                        break
                    time.sleep(1)
                assert job['status']=='succeeded',job.get('error_code')
                meta=job['result']
                assert meta['synthetic'] and not meta['degenerate'] and meta['prompt_id']==prompt['id']
                assert meta['support_raster']!=meta['source_raster']
                assert meta['query_window']=={'col_off':201,'row_off':307,'width':512,'height':512}
                assert abs(meta['affine'][0]-.00001)<1e-12
                objects.extend(meta[k] for k in ('probability_object','mask_object','valid_mask_object'))
                for kind in ('probability','mask','valid'):
                    url=client.get('/jobs/'+job['id']+'/artifacts/'+kind+'/download').raise_for_status().json()['url']
                    blob=httpx.get(url,timeout=20).raise_for_status().content
                    from rasterio.io import MemoryFile
                    with MemoryFile(blob) as memory,memory.open() as ds:
                        assert ds.shape==(512,512) and abs(ds.transform.a-.00001)<1e-12

                results=client.get(f'/projects/{project}/results',params={'job_id':job['id']}).raise_for_status().json()
                assert results and all(r['area_m2']>0 and r['mean_confidence']>=.5 for r in results)
                result=results[0]
                client.post('/results/'+result['id']+'/review',json={'action':'accepted'}).raise_for_status()
                exported=client.get('/jobs/'+job['id']+'/export').raise_for_status().json()
                assert len(exported['features'])==1 and exported['metadata']['model_release']==release
                with connection() as conn:
                    assert conn.execute('SELECT extensions.ST_IsValid(geometry),extensions.ST_SRID(geometry) FROM extraction_results WHERE id=%s',(result['id'],)).fetchone()==(True,4326)
                    assert conn.execute('SELECT count(*) FROM review_actions WHERE result_id=%s',(result['id'],)).fetchone()[0]==1
                (ROOT/'artifacts/p9-tile-acceptance.json').write_text(json.dumps({'synthetic':True,'real_model_acceptance':False,'metrics':meta,'result_count':len(results)},indent=2)+'\n')
                # Simulate a late response on an isolated test job, through the actual persistence helper.
                from geoai.tile_extraction import persist_tile_results
                import geoai.tile_extraction as tile_module
                from psycopg.rows import dict_row
                def local_database(_cfg):
                    conn=connection()
                    conn.row_factory=dict_row
                    return conn
                tile_module.database=local_database
                late_token=uuid.uuid4()
                with connection() as conn:
                    late_id=conn.execute("INSERT INTO jobs(project_id,created_by,idempotency_key,kind,raster_asset_id,prompt_id,model_endpoint_id,model_release_id,endpoint_revision,query_col,query_row,seed,status,claim_token) VALUES (%s,%s,%s,'geoextract_tile',%s,%s,%s,%s,%s,0,0,57,'cancelled',%s) RETURNING id",(project,uid,uuid.uuid4(),assets[1]['id'],prompt['id'],endpoint,release,selected['config_revision'],late_token)).fetchone()[0]
                late={'id':late_id,'project_id':project,'prompt_id':prompt['id'],'model_endpoint_id':endpoint,'endpoint_revision':selected['config_revision'],'claim_token':late_token}
                assert persist_tile_results(None,late,[(geometry,.8,.9)],{}) is False
                with connection() as conn:
                    conn.execute("UPDATE jobs SET status='running',claim_token=%s WHERE id=%s",(uuid.uuid4(),late_id))
                assert persist_tile_results(None,late,[(geometry,.8,.9)],{}) is False
                with connection() as conn:
                    assert conn.execute('SELECT count(*) FROM extraction_results WHERE job_id=%s',(late_id,)).fetchone()[0]==0
                with connection() as conn:
                    conn.execute('UPDATE geoai_internal.model_endpoints SET enabled=false WHERE id=%s',(endpoint,))
                replay=client.post(path,json=payload).raise_for_status().json()
                assert replay['id']==job['id']
                assert client.post(path,json={**payload,'idempotency_key':str(uuid.uuid4())}).status_code==422
                print('PASS: distinct support/query raster, native 512 window, registered HTTP inference, nonconstant probabilities, PostGIS, review and export; synthetic only')
        finally:
            for obj in objects:
                auth.request('DELETE','/storage/v1/object/'+env['STORAGE_BUCKET'],json={'prefixes':[obj]}).raise_for_status()
            with connection() as conn:
                if project:
                    conn.execute('DELETE FROM public.projects WHERE id=%s',(project,))
                if endpoint:
                    conn.execute('DELETE FROM geoai_internal.model_endpoints WHERE id=%s',(endpoint,))
                if release:
                    conn.execute('DELETE FROM geoai_internal.model_releases WHERE id=%s',(release,))
            if uid:
                auth.delete('/auth/v1/admin/users/'+uid).raise_for_status()


if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print('FAIL: '+type(exc).__name__+' '+str(exc)[:180] if isinstance(exc,AssertionError) else 'FAIL: '+type(exc).__name__+' (secrets suppressed)')
        raise SystemExit(1) from None

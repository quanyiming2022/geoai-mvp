"""Small-AOI capability acceptance using an isolated ordinary-owner project.
Usage: python scripts/acceptance_small_aoi.py setup|check|cleanup
Local credentials only; setup retains its fixture for subsequent browser checks.
"""
import json,sys,time,uuid
from pathlib import Path
import httpx,rasterio
from rasterio.warp import transform_geom
from dotenv import dotenv_values
from migrate import ROOT,connection
STATE=ROOT/'artifacts/small-aoi-state.json'
CREDS=Path('/tmp/geoai-small-aoi-browser.env')

def run(mode):
    env=dotenv_values(ROOT/'.env');api='http://127.0.0.1:'+env['GEOAI_API_PORT']
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':env['SERVICE_ROLE_KEY'],'Authorization':'Bearer '+env['SERVICE_ROLE_KEY']},timeout=60,trust_env=False) as admin,httpx.Client(base_url=api,timeout=180,trust_env=False) as c:
        if mode=='setup':
            assert not CREDS.exists(),'Existing acceptance fixture must be cleaned first'
            seed=uuid.uuid4().hex;credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
            uid=admin.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()['id']
            CREDS.write_text('EMAIL='+credentials['email']+'\nPASSWORD='+credentials['password']+'\n');CREDS.chmod(0o600)
            state={'uid':uid};STATE.write_text(json.dumps(state))
        else:state=json.loads(STATE.read_text())
        if mode=='cleanup':
            # Lock before touching storage: a browser user may have linked an
            # acceptance asset while it was visible in the shared library.
            with connection() as db:
                assert str(db.execute('SELECT owner_id FROM projects WHERE id=%s',(state['project'],)).fetchone()[0])==state['uid']
                assert db.execute("SELECT count(*) FROM jobs WHERE project_id=%s AND status IN ('queued','running')",(state['project'],)).fetchone()[0]==0
                assets=[str(r[0]) for r in db.execute('SELECT id FROM raster_assets WHERE project_id=%s FOR UPDATE',(state['project'],))]
                retained=[]
                for asset in assets:
                    referenced=db.execute("SELECT EXISTS(SELECT 1 FROM project_assets WHERE raster_asset_id=%s AND project_id<>%s) OR EXISTS(SELECT 1 FROM jobs WHERE raster_asset_id=%s AND project_id<>%s) OR EXISTS(SELECT 1 FROM visual_prompts WHERE raster_asset_id=%s AND project_id<>%s)",(asset,state['project'],asset,state['project'],asset,state['project'])).fetchone()[0]
                    if referenced:retained.append(asset)
                prefixes=[state['project']+'/rasters/'+asset+'/' for asset in retained]
                objects=[x[0] for x in db.execute("SELECT name FROM storage.objects WHERE bucket_id=%s AND split_part(name,'/',1)=%s",(env['STORAGE_BUCKET'],state['project'])).fetchall()]
                for name in objects:
                    if not any(name.startswith(prefix) for prefix in prefixes):
                        admin.request('DELETE','/storage/v1/object/'+env['STORAGE_BUCKET'],json={'prefixes':[name]}).raise_for_status()
                db.execute('DELETE FROM projects WHERE id=%s AND owner_id=%s',(state['project'],state['uid']))
                for asset in assets:
                    if asset in retained:
                        db.execute("UPDATE raster_assets SET deleted_at=CASE WHEN EXISTS(SELECT 1 FROM project_assets WHERE raster_asset_id=%s AND deleted_at IS NULL) THEN deleted_at ELSE now() END WHERE id=%s",(asset,asset))
                    else:db.execute('DELETE FROM raster_assets WHERE id=%s',(asset,))
                db.commit()
            admin.delete('/auth/v1/admin/users/'+state['uid']).raise_for_status();CREDS.unlink();print(f'PASS: isolated project/account cleaned; {len(retained)} externally referenced asset(s) and their files retained');return
        u=dotenv_values(CREDS);c.headers['Authorization']='Bearer '+c.post('/auth/login',json={'email':u['EMAIL'],'password':u['PASSWORD']}).raise_for_status().json()['access_token']
        if mode=='setup':
            state['project']=c.post('/projects',json={'name':'小范围完整分析 · 隔离验收'}).raise_for_status().json()['id'];STATE.write_text(json.dumps(state));base='/projects/'+state['project']
            source=ROOT/'artifacts/p9b-building/source-cog.tif'
            asset=c.post(base+'/rasters',headers={'X-Filename':'SPOT6-validation.tif'},content=source.read_bytes()).raise_for_status().json()
            for _ in range(150):
                asset=c.get(base+'/rasters').raise_for_status().json()[0]
                if asset['status'] in ('ready','failed'):break
                time.sleep(1)
            assert asset['status']=='ready';state['asset']=asset
            fixture=json.loads((ROOT/'artifacts/p9b-building/registered-run/fixtures.json').read_text())
            state['prompt']=c.post(base+'/prompts',json={**{k:fixture['prompt'][k] for k in ('name','class_label','description','geometry')},'raster_asset_id':asset['id']}).raise_for_status().json()
            state['aois']={}
            with rasterio.open(source) as ds:
                for label,x,y,w,h in [('small',975.25,960.5,18.5,19.75),('exact',730,715,512,512),('wide',730,715,513,100),('tall',730,715,100,513),('edge',0,0,50,50)]:
                    ring=[list(ds.transform*p) for p in [(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)]]
                    geometry=transform_geom(ds.crs,'EPSG:4326',{'type':'Polygon','coordinates':[ring]})
                    name={'small':'屋顶完整范围','exact':'单窗完整范围','wide':'宽度超限范围','tall':'高度超限范围','edge':'影像边缘范围'}[label]
                    state['aois'][label]=c.post(base+'/aois',json={'name':name,'geometry':geometry}).raise_for_status().json()
            STATE.write_text(json.dumps(state));print('PASS: isolated fixture ready',state['project']);return
        base='/projects/'+state['project'];proof={}
        context={'channel':'worker','raster_id':state['asset']['id'],'prompt_id':state['prompt']['id']}
        for label,aoi in state['aois'].items():
            ctx={**context,'aoi_id':aoi['id']}
            answer=c.post(base+'/assistant/agent',json={'text':'用这个样例提取整个范围里的建筑','workspace_context':ctx}).raise_for_status().json()
            proof[label]={'kind':answer['kind'],'execution_mode':answer['execution_mode'],'query_window':answer.get('query_window')}
            if label in ('wide','tall'):
                assert answer['code']=='CAPABILITY_NOT_AVAILABLE' and answer['execution_mode']=='multi_tile_full_aoi' and not answer.get('draft_id');continue
            assert answer['kind']=='draft' and answer['execution_mode']=='single_tile_full_aoi'
            assert not answer.get('suggested_actions') and answer['query_window']['available']
            # Existing plan endpoint must agree, without asking for coordinates.
            legacy=c.post(base+'/assistant/plan',json={'text':'扫描整个 AOI','workspace_context':{**ctx,'endpoint_id':answer['context_update']['endpoint_id']}}).raise_for_status().json();assert legacy['kind']=='draft' and legacy['execution_mode']=='single_tile_full_aoi'
            if label not in ('small','exact'):continue
            job=c.post(base+'/assistant/confirm',json={'draft_id':answer['draft_id'],'confirmed':True}).raise_for_status().json()
            for _ in range(150):
                job=c.get('/jobs/'+job['id']).raise_for_status().json()
                if job['status'] in ('succeeded','failed','cancelled'):break
                time.sleep(1)
            assert job['status']=='succeeded',job.get('error_code')
            with connection() as db:
                snapshot=db.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(job['id'],)).fetchone()[0]
                assert snapshot['query_window_pixel_offset']['width']==512 and snapshot['effective_analysis_geometry']
                outside=db.execute("SELECT count(*) FROM extraction_results WHERE job_id=%s AND NOT extensions.ST_IsEmpty(extensions.ST_Difference(geometry,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)))",(job['id'],json.dumps(snapshot['aoi_geometry_snapshot']))).fetchone()[0];assert outside==0
            proof[label].update(job_id=job['id'],result=job['result'],snapshot=snapshot)
        local=c.post(base+'/assistant/agent',json={'text':'在这里跑一下','workspace_context':{**context,'aoi_id':state['aois']['small']['id']}}).raise_for_status().json();assert local['kind']=='select_window'
        (ROOT/'artifacts/small-aoi-acceptance.json').write_text(json.dumps(proof,indent=2));print('PASS: small/exact full AOI automatic real jobs, wide/tall blocked, edge shift, explicit test asks location, snapshot and clipping')

if __name__=='__main__':run(sys.argv[1])

"""Real native-tile context vs effective AOI acceptance in an isolated project.
Usage: python scripts/acceptance_tile_aoi.py STATE_JSON CREDENTIAL_ENV
Only modifies resources in that explicit test project; retains job evidence until fixture cleanup.
"""
import json,sys,time,uuid
from pathlib import Path
import httpx,numpy as np,rasterio
from rasterio.warp import transform_geom,transform
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from dotenv import dotenv_values
from migrate import ROOT,connection


def run(state_path,credential_path):
    state=json.loads(Path(state_path).read_text());env=dotenv_values(ROOT/'.env');u=dotenv_values(credential_path)
    api='http://127.0.0.1:'+env['GEOAI_API_PORT'];token=httpx.post(api+'/auth/login',json={'email':u['EMAIL'],'password':u['PASSWORD']}).raise_for_status().json()['access_token']
    with rasterio.open(ROOT/'artifacts/p9b-building/source-cog.tif') as ds:
        ring=[list(ds.transform*p) for p in [(975.25,960.5),(993.75,960.5),(993.75,980.25),(975.25,980.25),(975.25,960.5)]]
        geometry=transform_geom(ds.crs,'EPSG:4326',{'type':'Polygon','coordinates':[ring]})
        def point(col,row):
            x,y=ds.transform*(col,row);a,b=transform(ds.crs,'EPSG:4326',[x],[y]);return {'longitude':a[0],'latitude':b[0]}
        inside=point(984,970);outside=point(900,900)
    base='/projects/'+state['project'];proof={}
    with httpx.Client(base_url=api,headers={'Authorization':'Bearer '+token},timeout=120,trust_env=False) as c:
        aoi=c.post(base+'/aois',json={'name':'AOI 有效范围验收','geometry':geometry}).raise_for_status().json();proof['aoi_id']=aoi['id']
        selection={'raster_id':state['asset']['id'],'aoi_id':aoi['id']}
        rejected=c.post(base+'/assistant/window',json={**selection,**outside});assert rejected.status_code==422 and '请选择 AOI 内的位置' in rejected.text
        window=c.post(base+'/assistant/window',json={**selection,**inside}).raise_for_status().json();assert window['width']==window['height']==512
        endpoint=next(e for e in c.get('/models/available-endpoints').raise_for_status().json() if e['model_name']=='SkySense++' and e['health_status']=='healthy')
        payload={'kind':'geoextract_tile','idempotency_key':str(uuid.uuid4()),'raster_asset_id':state['asset']['id'],'prompt_id':state['prompt']['id'],'model_endpoint_id':endpoint['id'],'model_release_id':endpoint['model_release_id'],'endpoint_revision':endpoint['config_revision'],'query_col':window['query_col'],'query_row':window['query_row'],'seed':42}
        full=c.post(base+'/jobs',json=payload).raise_for_status().json()
        clipped=c.post(base+'/jobs',json={**payload,'idempotency_key':str(uuid.uuid4()),'aoi_id':aoi['id']}).raise_for_status().json();proof['initial_status']=clipped['status']
        with connection() as db:
            before=db.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(clipped['id'],)).fetchone()[0]
            assert before['aoi']['id']==aoi['id']
            assert db.execute('SELECT extensions.ST_HausdorffDistance(extensions.ST_GeomFromGeoJSON(%s),extensions.ST_GeomFromGeoJSON(%s))',(json.dumps(before['aoi_geometry_snapshot']),json.dumps(geometry))).fetchone()[0]<1e-12
            geometry=before['aoi_geometry_snapshot']
            assert before['query_window_bounds']['type']=='Polygon'
        # Mutation after submission must not change the queued/running job input.
        changed=c.put(base+'/aois/'+aoi['id'],json={'name':aoi['name'],'description':'modified after submission','geometry':state['aoi']['geometry'],'expected_revision':aoi['revision']}).raise_for_status().json()
        c.request('DELETE',base+'/aois/'+aoi['id'],json={'expected_revision':changed['revision']}).raise_for_status()
        for job in (full,clipped):
            for _ in range(150):
                finished=c.get('/jobs/'+job['id']).raise_for_status().json()
                if finished['status'] in ('succeeded','failed','cancelled'):break
                time.sleep(1)
            assert finished['status']=='succeeded',finished.get('error_code');job.update(finished)
        assert full['result']['input_digests']==clipped['result']['input_digests']
        arrays={}
        for job,label in ((full,'full'),(clipped,'clipped')):
            for kind in ('probability','mask','valid'):
                link=c.get('/jobs/'+job['id']+'/artifacts/'+kind+'/download').raise_for_status().json()['url']
                blob=httpx.get(link,timeout=30,trust_env=False).raise_for_status().content
                (ROOT/f'artifacts/aoi-window-{label}-{kind}.tif').write_bytes(blob)
                with MemoryFile(blob) as mem,mem.open() as ds:
                    values=ds.read(1);arrays[label,kind]=values
                    if label=='clipped':
                        valid=geometry_mask([transform_geom('EPSG:4326',ds.crs,geometry)],out_shape=(512,512),transform=ds.transform,invert=True)
                        if kind=='probability':assert np.isnan(values[~valid]).all()
                        else:assert not values[~valid].any()
        effective=arrays['clipped','valid'].astype(bool)
        assert np.array_equal(arrays['full','probability'][effective],arrays['clipped','probability'][effective])
        results=c.get(base+'/results',params={'job_id':clipped['id']}).raise_for_status().json();assert results,'Expected roof response within small AOI'
        with connection() as db:
            now=db.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(clipped['id'],)).fetchone()[0];assert now==before
            covered,count,area=db.execute("SELECT bool_and(extensions.ST_IsEmpty(extensions.ST_Difference(geometry,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)))),count(*),sum(area_m2) FROM extraction_results WHERE job_id=%s",(json.dumps(geometry),clipped['id'])).fetchone();assert covered and count==len(results)
            aoi_area=db.execute('SELECT extensions.ST_Area(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)::extensions.geography)',(json.dumps(geometry),)).fetchone()[0];assert area<=aoi_area+1e-6
        # These are isolated validation predictions, explicitly reviewed only for export verification.
        for result in results:c.post('/results/'+result['id']+'/review',json={'action':'accepted'}).raise_for_status()
        exported=c.get('/jobs/'+clipped['id']+'/export').raise_for_status().json();assert len(exported['features'])==len(results)
        (ROOT/'artifacts/aoi-window-export.geojson').write_text(json.dumps(exported,indent=2))
        with connection() as db:
            for feature in exported['features']:
                assert db.execute('SELECT extensions.ST_IsEmpty(extensions.ST_Difference(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326),extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)))',(json.dumps(feature['geometry']),json.dumps(geometry))).fetchone()[0]
        proof.update(full_job=full['id'],clipped_job=clipped['id'],window=window,geometry=geometry,input_digests_equal=True,probability_inside_exact=True,postgis_outside_empty=True,export_outside_empty=True,snapshot_unchanged=True,result_count=len(results),area_m2=area,aoi_area_m2=aoi_area,metrics=clipped['result'])
        (ROOT/'artifacts/aoi-window-real-acceptance.json').write_text(json.dumps(proof,indent=2))
        print('PASS: outside point rejected; native model inputs identical; small AOI mask + exact PostGIS intersection; review/export inside AOI; submitted snapshot survives later AOI edit/delete')

if __name__=='__main__':run(*sys.argv[1:])

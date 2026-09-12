"""Opt-in P9 native-resolution HTTP inference; no dependency on P8 preview crops."""
import hashlib
import json
import numpy as np
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
from rasterio.io import MemoryFile
from rasterio.features import shapes,geometry_mask
from rasterio.warp import transform_geom
from .raster_worker import database
from .rasters import provider as storage_provider
from .native_tile import read_native_tile,read_support_tile
from .lan_compute import LanHttpComputeProvider
from .endpoints import allowed_hosts
from .worker_contract import ImagePayload,ModelWorkerRequest,ModelWorkerError,probability_metrics


def endpoint_for_job(cfg,row):
    with database(cfg) as conn:
        endpoint=conn.execute('SELECT e.*,r.model_name,r.model_version,r.checkpoint_digest FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r ON r.id=e.model_release_id WHERE e.id=%s AND e.model_release_id=%s AND e.config_revision=%s AND e.enabled',(row['model_endpoint_id'],row['model_release_id'],row['endpoint_revision'])).fetchone()
    if not endpoint or endpoint['provider_type']!='lan_http':
        raise ModelWorkerError('endpoint_unreachable')
    return endpoint


def tile_polygons(probability,valid,transform,crs):
    binary=((probability>=.5)&valid).astype('uint8')
    polygons=[]
    for geometry,value in shapes(binary,mask=binary.astype(bool),transform=transform):
        if value!=1:
            continue
        inside=geometry_mask([geometry],out_shape=(512,512),transform=transform,invert=True)&valid
        scores=probability[inside]
        polygons.append((transform_geom(crs,'EPSG:4326',geometry),float(scores.mean()),float(scores.max())))
        if len(polygons)>1000:
            raise ModelWorkerError('invalid_response')
    return binary,polygons


def effective_valid_mask(valid,transform,crs,aoi_geometry=None):
    if not aoi_geometry:return valid
    shape=transform_geom('EPSG:4326',crs,aoi_geometry)
    return valid & geometry_mask([shape],out_shape=valid.shape,transform=transform,invert=True)


def geotiff(values,transform,crs):
    with MemoryFile() as memory:
        with memory.open(driver='GTiff',height=512,width=512,count=1,dtype=values.dtype,crs=crs,transform=transform,compress='deflate',nodata=float('nan') if np.issubdtype(values.dtype,np.floating) and np.isnan(values).any() else None) as ds:
            ds.write(values,1)
        return memory.read()


def persist_tile_results(cfg,row,polygons,metadata):
    with database(cfg) as conn:
        # Configuration and job locks fence changes/cancellation while committing GIS output.
        endpoint=conn.execute('SELECT id FROM geoai_internal.model_endpoints WHERE id=%s AND config_revision=%s AND enabled FOR SHARE',(row['model_endpoint_id'],row['endpoint_revision'])).fetchone()
        current=conn.execute("SELECT id FROM jobs WHERE id=%s AND claim_token=%s AND status='running' FOR UPDATE",(row['id'],row['claim_token'])).fetchone()
        if not endpoint or not current:
            return False
        count=0
        for geometry,mean,maximum in polygons:
            effective=[(geometry,None)]
            aoi=metadata.get('aoi_geometry_snapshot')
            if aoi:
                clipped=conn.execute("SELECT extensions.ST_AsGeoJSON((d).geom,17)::json AS geometry,extensions.ST_AsEWKB((d).geom) AS wkb FROM extensions.ST_Dump(extensions.ST_CollectionExtract(extensions.ST_Intersection(extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326),extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)),3)) d WHERE NOT extensions.ST_IsEmpty((d).geom) AND extensions.ST_Area((d).geom)>0",(json.dumps(geometry),json.dumps(aoi))).fetchall()
                effective=[(item['geometry'],bytes(item['wkb'])) for item in clipped]
            for clipped_geometry,wkb in effective:
                result_metadata={**metadata,'effective_prediction_geometry':clipped_geometry}
                geometry_sql='extensions.ST_GeomFromEWKB(%s)' if wkb else 'extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)'
                conn.execute(f'INSERT INTO extraction_results(project_id,job_id,prompt_id,geometry,mean_confidence,max_confidence,source_metadata) VALUES (%s,%s,%s,{geometry_sql},%s,%s,%s)',(row['project_id'],row['id'],row['prompt_id'],wkb if wkb else json.dumps(clipped_geometry),mean,maximum,Jsonb(result_metadata)))
                count+=1
        merged=conn.execute('SELECT extensions.ST_AsGeoJSON(extensions.ST_UnaryUnion(extensions.ST_Collect(geometry)),17)::json AS geometry FROM extraction_results WHERE job_id=%s',(row['id'],)).fetchone()['geometry']
        conn.execute("UPDATE jobs SET status='succeeded',progress=100,finished_at=now(),result=%s WHERE id=%s",(Jsonb({**metadata,'result_count':count,'effective_prediction_geometry':merged}),row['id']))
        return True


def execute_tile(cfg,row):
    endpoint=endpoint_for_job(cfg,row)
    compute=LanHttpComputeProvider(endpoint,allowed_hosts=allowed_hosts())
    storage=storage_provider(cfg,internal=True)
    try:
        health=compute.healthcheck()['model_info']
        if any(health.get(k)!=endpoint[k] for k in ('model_name','model_version','checkpoint_digest')):
            raise ModelWorkerError('invalid_response')
        frozen=row.get('execution_snapshot')
        if not frozen:
            raise ModelWorkerError('inference_failed')
        inputs={'support_raster':frozen['prompt']['raster_asset_id'],
                'geometry':frozen['prompt']['geometry'],
                'support_key':frozen['support_raster']['cog_object_key'],
                'support_ranges':frozen['support_raster']['display_ranges'],
                'query_key':frozen['query_raster']['cog_object_key'],
                'query_ranges':frozen['query_raster']['display_ranges']}
        for role,raster in [('support',inputs['support_raster']),('query',row['raster_asset_id'])]:
            origin=frozen[role+'_raster'].get('storage_project_id',row['project_id'])
            if inputs[role+'_key']!=f"{origin}/rasters/{raster}/cog.tif":
                raise ModelWorkerError('inference_failed')
        support,mask,support_window=read_support_tile(storage.create_signed_url(cfg.storage_bucket,inputs['support_key'],60),inputs['geometry'],inputs['support_ranges'])
        query,valid,transform,crs=read_native_tile(storage.create_signed_url(cfg.storage_bucket,inputs['query_key'],60),row['query_col'],row['query_row'],inputs['query_ranges'])
        if not valid.any():
            raise ModelWorkerError('inference_failed')
        request=ModelWorkerRequest(job_id=row['id'],attempt_id=row['claim_token'],model_release_id=row['model_release_id'],seed=row['seed'],support_image=ImagePayload.from_pixels(support),support_mask=ImagePayload.from_pixels(mask),query_image=ImagePayload.from_pixels(query))
        response=compute.execute(request)
        probability=response.probabilities()
        stats=probability_metrics(probability[valid])
        if stats['degenerate']:
            # Persist diagnostics as failure, never publish degenerate output as accepted inference.
            with database(cfg) as conn:
                conn.execute("UPDATE jobs SET status='failed',error_code='invalid_response',finished_at=now(),result=%s WHERE id=%s AND claim_token=%s AND status='running'",(Jsonb({**stats,'reason':'degenerate_probability','checkpoint_digest':response.checkpoint_digest,'seed':row['seed'],'runtime_ms':response.runtime_ms,'endpoint_id':str(row['model_endpoint_id']),'model_release_id':str(row['model_release_id']),'model_name':response.model_name,'model_version':response.model_version,'gpu_memory_peak':response.metadata.get('gpu_memory_peak'),'slot_id':response.metadata.get('slot_id')}),row['id'],row['claim_token']))
            return
        aoi_geometry=frozen.get('aoi_geometry_snapshot') or (frozen.get('aoi') or {}).get('geometry')
        effective_valid=effective_valid_mask(valid,transform,crs,aoi_geometry)
        binary,polygons=tile_polygons(probability,effective_valid,transform,crs)
        from .map_window import transformed_footprint
        query_bounds=transformed_footprint(transform,crs)
        saved_bounds=frozen.get('query_window_bounds')
        if saved_bounds and not np.allclose(np.asarray(saved_bounds['coordinates']),np.asarray(query_bounds['coordinates']),rtol=0,atol=1e-10):raise ModelWorkerError('inference_failed')
        prefix=f"{row['project_id']}/jobs/{row['id']}/{row['claim_token']}"
        metadata={**stats,'aoi_geometry_snapshot':aoi_geometry,'query_window_bounds':query_bounds,'effective_prediction_rule':'prediction intersect AOI' if aoi_geometry else 'prediction intersect valid source','model':response.model_name,'model_version':response.model_version,'model_release_id':str(row['model_release_id']),'endpoint_id':str(row['model_endpoint_id']),'checkpoint_digest':response.checkpoint_digest,'usage_policy':endpoint['usage_policy'],'synthetic':health.get('synthetic',False),'runtime_ms':response.runtime_ms,'gpu_memory_peak':response.metadata.get('gpu_memory_peak'),'seed':row['seed'],'slot_id':response.metadata.get('slot_id'),'prompt_id':str(row['prompt_id']),'prompt_version':str(frozen['prompt']['revision']),'prompt_name':frozen['prompt']['name'],'prompt_class':frozen['prompt']['class_label'],'input_capture_basis':frozen['capture_basis'],'support_raster':str(inputs['support_raster']),'source_raster':str(row['raster_asset_id']),'support_window':support_window,'query_window':{'col_off':row['query_col'],'row_off':row['query_row'],'width':512,'height':512},'source_crs':crs,'affine':list(transform)[:6],'threshold':.5,'output_crs':'EPSG:4326','generation_time':datetime.now(timezone.utc).isoformat(),'probability_object':prefix+'/probability.tif','mask_object':prefix+'/mask.tif','valid_mask_object':prefix+'/valid.tif','input_digests':{k:hashlib.sha256(getattr(request,k).data.encode()).hexdigest() for k in ('support_image','support_mask','query_image')}}
        # Publish only effective pixels; complete model probability remains in memory.
        output_probability=np.where(effective_valid,probability,np.nan).astype('float32') if aoi_geometry else probability
        if aoi_geometry:
            metadata.update(mask_area=int(binary.sum()),foreground_ratio=float(binary.sum()/effective_valid.sum()) if effective_valid.any() else 0,probability_mean=float(probability[effective_valid].mean()) if effective_valid.any() else None,probability_std=float(probability[effective_valid].std()) if effective_valid.any() else None,effective_valid_pixels=int(effective_valid.sum()))
        for key,values in [('probability_object',output_probability),('mask_object',binary),('valid_mask_object',effective_valid.astype('uint8'))]:
            storage.put_object(cfg.storage_bucket,metadata[key],geotiff(values,transform,crs),'image/tiff')
        # On uncertain DB outcome retain immutable objects; they cannot appear without a fenced row.
        persist_tile_results(cfg,row,polygons,metadata)
    finally:
        compute.close()
        storage.close()


def cancel_remote(cfg,row):
    if row['kind']!='geoextract_tile':
        return
    compute=None
    try:
        compute=LanHttpComputeProvider(endpoint_for_job(cfg,row),allowed_hosts=allowed_hosts())
        compute.cancel(row['id'],row['claim_token'])
    except Exception:
        pass  # Local fencing is authoritative even when remote cancellation is unreachable.
    finally:
        if compute:
            compute.close()

"""Mock GeoExtract: real geospatial I/O, deliberately synthetic model probabilities."""
import json
from datetime import datetime, timezone
import numpy as np
from rasterio.io import MemoryFile
from rasterio.features import shapes
from rasterio.warp import transform_geom
from psycopg.types.json import Jsonb
from .raster_worker import database
from .rasters import provider
from .prompt_processing import support_crop
from .models import MockAdapter
from .compute import MockComputeProvider


def mock_polygons(query_image,query_mask,support_image,support_mask):
    with MemoryFile(query_image) as qim, MemoryFile(query_mask) as qmm, MemoryFile(support_image) as sim, MemoryFile(support_mask) as smm:
        with qim.open() as q, qmm.open() as mask, sim.open() as si, smm.open() as sm:
            if q.crs!=mask.crs or q.transform!=mask.transform or q.shape!=mask.shape or si.crs!=sm.crs or si.transform!=sm.transform or si.shape!=sm.shape:
                raise ValueError('sample_grid_mismatch')
            if max(q.width,q.height,si.width,si.height)>512 or q.count>16 or si.count>16 or sm.count!=1 or mask.count!=1:
                raise ValueError('sample_dimensions_exceeded')
            support=sm.read(1)
            if not np.any(support==1) or not set(np.unique(support)) <= {0,1}:
                raise ValueError('invalid_support_mask')
            compute=MockComputeProvider(MockAdapter())
            output=compute.execute({'width':q.width,'height':q.height,'image':q.read()}, {'support_image':si.read(),'support_mask':support.reshape(-1).tolist()})
            probability=np.asarray(output['probabilities'],dtype='float32').reshape(q.height,q.width)
            positive=((probability>=.5)&(mask.read(1)==1)).astype('uint8')
            polygons=[]
            for geometry,value in shapes(positive,mask=positive.astype(bool),transform=q.transform):
                if value!=1:
                    continue
                polygons.append(transform_geom(q.crs,'EPSG:4326',geometry))
                if len(polygons)>1000:
                    raise ValueError('too_many_mock_regions')
            if not polygons:
                raise ValueError('empty_mock_result')
            return polygons


def execute_extraction(cfg,row):
    with database(cfg) as conn:
        inputs=conn.execute("SELECT r.cog_object_key,r.bucket,p.support_image_object,p.support_mask_object,extensions.ST_AsGeoJSON(a.geometry)::json AS aoi FROM raster_assets r JOIN visual_prompts p ON p.raster_asset_id=r.id AND p.project_id=r.project_id JOIN aois a ON a.project_id=r.project_id WHERE r.id=%s AND p.id=%s AND a.id=%s AND r.project_id=%s AND r.status='ready'",(row['raster_asset_id'],row['prompt_id'],row['aoi_id'],row['project_id'])).fetchone()
    if not inputs:
        raise ValueError('inputs_unavailable')
    prefix=f"{row['project_id']}/"
    expected=[prefix+f"rasters/{row['raster_asset_id']}/cog.tif",prefix+f"prompts/{row['prompt_id']}/image.tif",prefix+f"prompts/{row['prompt_id']}/mask.tif"]
    if inputs['bucket']!=cfg.storage_bucket or [inputs['cog_object_key'],inputs['support_image_object'],inputs['support_mask_object']]!=expected:
        raise ValueError('invalid_input_storage_reference')
    storage=provider(cfg,internal=True)
    try:
        # Validate size before loading bounded support artifacts.
        for key in expected[1:]:
            if storage.head_object(cfg.storage_bucket,key)['size']>64*1024*1024:
                raise ValueError('support_artifact_too_large')
        support_image=storage.get_object(cfg.storage_bucket,expected[1])
        support_mask=storage.get_object(cfg.storage_bucket,expected[2])
        image,mask,crs=support_crop(storage.create_signed_url(cfg.storage_bucket,expected[0],60),inputs['aoi'])
        polygons=mock_polygons(image,mask,support_image,support_mask)
    finally:
        storage.close()
    metadata={'mock':True,'model_release':'mock-v1','source_raster':str(row['raster_asset_id']),'job_id':str(row['id']),'prompt_id':str(row['prompt_id']),'aoi_id':str(row['aoi_id']),'source_crs':crs,'output_crs':'EPSG:4326','generation_time':datetime.now(timezone.utc).isoformat()}
    persist_results(cfg,row,polygons,metadata)


def persist_results(cfg,row,polygons,metadata):
    # One transaction locks the fenced job before writing any original predictions.
    with database(cfg) as conn:
        current=conn.execute("SELECT id FROM jobs WHERE id=%s AND claim_token=%s AND status='running' FOR UPDATE",(row['id'],row['claim_token'])).fetchone()
        if not current:
            return
        for geometry in polygons:
            conn.execute("INSERT INTO extraction_results(project_id,job_id,prompt_id,geometry,mean_confidence,max_confidence,source_metadata) VALUES (%s,%s,%s,extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326),.75,.75,%s)",(row['project_id'],row['id'],row['prompt_id'],json.dumps(geometry),Jsonb(metadata)))
        conn.execute("UPDATE jobs SET status='succeeded',progress=100,finished_at=now(),result=%s WHERE id=%s",(Jsonb({'mock':True,'model':'mock-v1','result_count':len(polygons)}),row['id']))

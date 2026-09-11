from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from .auth import CurrentUser
from .spatial import UserSQLRepository
from .projects import accessible
from .jobs import JobRepository


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['accepted','rejected']


class ResultRepository(UserSQLRepository):
    columns='id,project_id,job_id,prompt_id,extensions.ST_AsGeoJSON(geometry)::json AS geometry,area_m2,extensions.ST_Perimeter(geometry::extensions.geography) AS perimeter_m,mean_confidence,max_confidence,review_status,source_metadata,created_at'

    def list(self,project_id,job_id=None):
        return self.execute(f"SELECT {self.columns} FROM extraction_results WHERE project_id=%s AND job_id=COALESCE(%s::uuid,(SELECT id FROM jobs WHERE project_id=%s AND kind IN ('geoextract','geoextract_tile') AND status='succeeded' ORDER BY created_at DESC LIMIT 1)) ORDER BY created_at,id",(project_id,job_id,project_id))

    def review(self,result_id,action):
        if not self.execute('SELECT id FROM extraction_results WHERE id=%s',(result_id,)):
            raise HTTPException(404,'Result not found')
        rows=self.execute(f'UPDATE extraction_results SET review_status=%s WHERE id=%s RETURNING {self.columns}',(action,result_id))
        if not rows:
            raise HTTPException(403,'Review requires editor access')
        return rows[0]

    def export(self,job_id):
        rows=self.execute(f"SELECT {self.columns} FROM extraction_results WHERE job_id=%s AND review_status='accepted' ORDER BY id",(job_id,))
        return {'type':'FeatureCollection','features':[{'type':'Feature','id':str(row['id']),'geometry':row['geometry'],'properties':{key:value for key,value in row.items() if key not in ('geometry','id')}} for row in rows]}


router=APIRouter(tags=['results'])


@router.get('/projects/{project_id}/results')
def list_results(project_id: UUID,current: CurrentUser,job_id: UUID | None = None):
    accessible(project_id,current)
    return ResultRepository(current.user['id']).list(project_id,job_id)


@router.post('/results/{result_id}/review')
def review_result(result_id: UUID,data: ReviewInput,current: CurrentUser):
    return ResultRepository(current.user['id']).review(result_id,data.action)


@router.get('/jobs/{job_id}/export')
def export_result(job_id: UUID,current: CurrentUser):
    job=JobRepository(current.user['id']).get(job_id)
    if job['kind'] not in ('geoextract','geoextract_tile') or job['status']!='succeeded':
        raise HTTPException(409,'Only completed GeoExtract jobs can be exported')
    result=ResultRepository(current.user['id']).export(job_id)
    result['metadata']={'job_id':str(job_id),'source_raster':str(job['raster_asset_id']),'model_release':'mock-v1','crs':'EPSG:4326','review_filter':'accepted','generation_time':job['finished_at']}
    if job['kind']=='geoextract_tile':
        result['metadata'].update(job['result'] or {})
        result['metadata']['model_release']=str(job['model_release_id'])
    return result


@router.get('/jobs/{job_id}/artifacts/{kind}/download')
def download_tile_artifact(job_id:UUID,kind:Literal['probability','mask','valid'],current:CurrentUser):
    from .config import Settings
    from .rasters import provider
    job=JobRepository(current.user['id']).get(job_id)
    if job['kind']!='geoextract_tile' or job['status']!='succeeded':
        raise HTTPException(409,'Artifact unavailable')
    key=(job['result'] or {}).get({'probability':'probability_object','mask':'mask_object','valid':'valid_mask_object'}[kind])
    prefix=f"{job['project_id']}/jobs/{job_id}/"
    if not isinstance(key,str) or not key.startswith(prefix):
        raise HTTPException(409,'Artifact identity unavailable')
    suffix=key[len(prefix):].split('/')
    try:
        if len(suffix)!=2 or suffix[1]!=kind+'.tif':
            raise ValueError()
        UUID(suffix[0])
    except ValueError:
        raise HTTPException(409,'Invalid artifact identity') from None
    cfg=Settings()
    storage=provider(cfg)
    try:
        return {'url':storage.create_signed_url(cfg.storage_bucket,key,60)}
    finally:
        storage.close()

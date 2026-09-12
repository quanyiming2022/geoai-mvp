from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .auth import CurrentUser
from .spatial import UserSQLRepository, PolygonInput
from .projects import accessible
from .jobs import JobRepository


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    action: Literal['accepted','rejected']


def result_feature(row):
    metadata=row.get('source_metadata') or {}
    properties={key:value for key,value in row.items() if key not in ('geometry','id')}
    properties.update(source_job_id=str(row['job_id']),model_name=metadata.get('model'),model_version=metadata.get('model_version',metadata.get('model_release')),checkpoint_digest=metadata.get('checkpoint_digest'))
    return {'type':'Feature','id':str(row['id']),'geometry':row['geometry'],'properties':properties}


class ResultRepository(UserSQLRepository):
    columns='result_name,description,revision,updated_at,updated_by,id,project_id,job_id,prompt_id,extensions.ST_AsGeoJSON(COALESCE(current_geometry,geometry),CASE WHEN source_metadata->\'aoi_geometry_snapshot\' <> \'null\'::jsonb THEN 17 ELSE 9 END)::json AS geometry,extensions.ST_Area(COALESCE(current_geometry,geometry)::extensions.geography) AS area_m2,extensions.ST_Perimeter(COALESCE(current_geometry,geometry)::extensions.geography) AS perimeter_m,mean_confidence,max_confidence,review_status,source_metadata,created_at'

    def list(self,project_id,job_id=None):
        return self.execute(f"SELECT {self.columns} FROM extraction_results WHERE deleted_at IS NULL AND project_id=%s AND job_id=COALESCE(%s::uuid,(SELECT id FROM jobs WHERE project_id=%s AND kind IN ('geoextract','geoextract_tile') AND status='succeeded' ORDER BY created_at DESC LIMIT 1)) ORDER BY created_at,id",(project_id,job_id,project_id))

    def review(self,result_id,action):
        if not self.execute('SELECT id FROM extraction_results WHERE deleted_at IS NULL AND id=%s',(result_id,)):
            raise HTTPException(404,'Result not found')
        rows=self.execute(f'UPDATE extraction_results SET review_status=%s WHERE deleted_at IS NULL AND id=%s RETURNING {self.columns}',(action,result_id))
        if not rows:
            raise HTTPException(403,'Review requires editor access')
        return rows[0]

    def export(self,job_id):
        rows=self.execute(f"SELECT {self.columns} FROM extraction_results WHERE deleted_at IS NULL AND job_id=%s AND review_status='accepted' ORDER BY id",(job_id,))
        return {'type':'FeatureCollection','features':[result_feature(row) for row in rows]}


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


class ResultEdit(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=1,strict=True)
    result_name:str|None=Field(default=None,min_length=1,max_length=120)
    description:str|None=Field(default=None,max_length=2000)
    geometry:PolygonInput|None=None

class ResultDelete(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_revision:int=Field(ge=1,strict=True)
    confirmed:Literal[True]


def mutate_result(result_id,current,data,delete=False):
    repo=ResultRepository(current.user['id'])
    rows=repo.execute("SELECT revision,geoai_internal.project_role(project_id) AS role FROM public.extraction_results WHERE id=%s AND deleted_at IS NULL",(result_id,))
    if not rows:raise HTTPException(404,'Result not found')
    if rows[0]['role'] not in ('owner','editor'):raise HTTPException(403,'Editor access required')
    if rows[0]['revision']!=data.expected_revision:raise HTTPException(409,'Result changed; refresh before editing')
    if delete:
        assignments="deleted_at=now()";params=[]
    else:
        fields=[];params=[]
        for field in ('result_name','description'):
            value=getattr(data,field)
            if value is not None:fields.append(field+'=%s');params.append(value)
        if data.geometry is not None:
            fields.append('current_geometry=extensions.ST_SetSRID(extensions.ST_GeomFromGeoJSON(%s),4326)');params.append(data.geometry.model_dump_json())
        if not fields:raise HTTPException(422,'No changes supplied')
        assignments=','.join(fields)
    changed=repo.execute(f"UPDATE public.extraction_results SET {assignments} WHERE id=%s AND revision=%s AND deleted_at IS NULL RETURNING {repo.columns}",(*params,result_id,data.expected_revision))
    if not changed:raise HTTPException(409,'Result changed; refresh before editing')
    return changed[0]

@router.patch('/results/{result_id}')
def edit_result(result_id:UUID,data:ResultEdit,current:CurrentUser):
    return mutate_result(result_id,current,data)

@router.delete('/results/{result_id}')
def delete_result(result_id:UUID,data:ResultDelete,current:CurrentUser):
    mutate_result(result_id,current,data,True)
    return {'ok':True}

@router.get('/results/{result_id}/revisions')
def revisions(result_id:UUID,current:CurrentUser):
    return ResultRepository(current.user['id']).execute('SELECT revision,operation,before_state,after_state,updated_by,created_at FROM public.result_revisions WHERE result_id=%s ORDER BY revision',(result_id,))

@router.get('/results/{result_id}/export')
def export_one(result_id:UUID,current:CurrentUser):
    repo=ResultRepository(current.user['id'])
    rows=repo.execute(f'SELECT {repo.columns} FROM public.extraction_results WHERE id=%s AND deleted_at IS NULL',(result_id,))
    if not rows:raise HTTPException(404,'Result not found')
    row=rows[0]
    return {'type':'FeatureCollection','name':row['result_name'],'features':[result_feature(row)]}

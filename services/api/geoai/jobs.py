from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from redis import Redis
from .auth import CurrentUser
from .config import Settings
from .projects import accessible
from .spatial import UserSQLRepository


class JobInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['diagnostic','geoextract','geoextract_tile'] = 'diagnostic'
    idempotency_key: UUID
    raster_asset_id: UUID | None = None
    prompt_id: UUID | None = None
    aoi_id: UUID | None = None

    model_endpoint_id: UUID | None = None
    model_release_id: UUID | None = None
    endpoint_revision: int | None = Field(default=None,ge=1,strict=True)
    query_col: int | None = Field(default=None,ge=0,le=2147483135,strict=True)
    query_row: int | None = Field(default=None,ge=0,le=2147483135,strict=True)
    seed: int | None = Field(default=None,ge=0,le=4294967295,strict=True)

    @model_validator(mode='after')
    def valid_references(self):
        refs=(self.raster_asset_id,self.prompt_id,self.aoi_id)
        if (self.kind=='geoextract' and not all(refs)) or (self.kind=='diagnostic' and any(refs)):
            raise ValueError('Job inputs do not match kind')
        tile=(self.model_endpoint_id,self.model_release_id,self.endpoint_revision,self.query_col,self.query_row,self.seed)
        if self.kind=='geoextract_tile':
            if not self.raster_asset_id or not self.prompt_id or self.aoi_id or any(v is None for v in tile):
                raise ValueError('Single tile requires a prompt, query window and registered endpoint')
        elif any(v is not None for v in tile):
            raise ValueError('Tile parameters are only valid for the tile workflow')
        return self


class JobRepository(UserSQLRepository):
    columns = 'model_endpoint_id,model_release_id,endpoint_revision,query_col,query_row,seed,id,project_id,created_by,kind,status,progress,attempts,result,error_code,created_at,started_at,finished_at,raster_asset_id,prompt_id,aoi_id'

    def list(self,project_id,offset=0):
        return self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s ORDER BY created_at DESC,id LIMIT 50 OFFSET %s',(project_id,offset))

    def get(self,job_id):
        rows=self.execute(f'SELECT {self.columns} FROM jobs WHERE id=%s',(job_id,))
        if not rows:
            raise HTTPException(404,'Job not found')
        return rows[0]

    def create(self,project_id,data):
        # A retry with the same key returns the original frozen submission even
        # if its current resources were later edited/deleted.
        fields=('raster_asset_id','prompt_id','aoi_id','model_endpoint_id','model_release_id','endpoint_revision','query_col','query_row','seed')
        prior=self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s AND created_by=%s AND idempotency_key=%s',(project_id,self.user_id,data.idempotency_key))
        if prior:
            if prior[0]['kind']!=data.kind or any(str(prior[0][f])!=str(getattr(data,f)) for f in fields):
                if data.kind=='geoextract' and not self.execute("SELECT r.id FROM raster_assets r JOIN visual_prompts p ON p.raster_asset_id=r.id JOIN aois a ON a.project_id=r.project_id WHERE r.id=%s AND p.id=%s AND a.id=%s AND r.project_id=%s AND p.deleted_at IS NULL AND a.deleted_at IS NULL AND r.status='ready' AND extensions.ST_Covers(r.footprint,a.geometry)",(data.raster_asset_id,data.prompt_id,data.aoi_id,project_id)):
                    raise HTTPException(422,'Select a ready raster, its prompt and an AOI inside the raster')
                raise HTTPException(409,'Idempotency key conflicts with another request')
            return prior[0]

        if data.kind=='geoextract':
            rows=self.execute("SELECT r.id FROM raster_assets r JOIN visual_prompts p ON p.raster_asset_id=r.id JOIN aois a ON a.project_id=r.project_id WHERE r.id=%s AND p.id=%s AND a.id=%s AND r.project_id=%s AND p.deleted_at IS NULL AND a.deleted_at IS NULL AND r.status='ready' AND extensions.ST_Covers(r.footprint,a.geometry)",(data.raster_asset_id,data.prompt_id,data.aoi_id,project_id))
            if not rows:
                raise HTTPException(422,'Select a ready raster, its prompt and an AOI inside the raster')
        if data.kind=='geoextract_tile':
            fields=('raster_asset_id','prompt_id','model_endpoint_id','model_release_id','endpoint_revision','query_col','query_row','seed')
            existing=self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s AND created_by=%s AND idempotency_key=%s',(project_id,self.user_id,data.idempotency_key))
            if existing:
                if existing[0]['kind']!=data.kind or any(str(existing[0][f])!=str(getattr(data,f)) for f in fields):
                    raise HTTPException(409,'Idempotency key conflicts with another request')
                return existing[0]
            if not self.execute("SELECT p.id FROM visual_prompts p JOIN raster_assets s ON s.id=p.raster_asset_id WHERE p.id=%s AND p.project_id=%s AND p.deleted_at IS NULL AND s.status='ready' AND s.width>=512 AND s.height>=512 AND s.bands>=3",(data.prompt_id,project_id)):
                raise HTTPException(422,'Select a reusable prompt with a ready RGB source at least 512 pixels wide and high')
            from .endpoint_monitor import require_live_endpoint
            if self.execute('SELECT geoai_internal.project_role(%s) AS role',(project_id,))[0]['role'] not in ('owner','editor'):
                raise HTTPException(403,'Editor access required')
            require_live_endpoint(data.model_endpoint_id,data.endpoint_revision)
            fields=('raster_asset_id','prompt_id','model_endpoint_id','model_release_id','endpoint_revision','query_col','query_row','seed')
            rows=self.execute(f"INSERT INTO jobs(project_id,created_by,idempotency_key,kind,{','.join(fields)}) VALUES ({','.join(['%s']*(4+len(fields)))}) ON CONFLICT DO NOTHING RETURNING {self.columns}",(project_id,self.user_id,data.idempotency_key,data.kind,*(getattr(data,f) for f in fields)))
            if rows:
                return rows[0]
            existing=self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s AND created_by=%s AND idempotency_key=%s',(project_id,self.user_id,data.idempotency_key))
            if not existing or existing[0]['kind']!=data.kind or any(str(existing[0][f])!=str(getattr(data,f)) for f in fields):
                raise HTTPException(409,'Idempotency key conflicts with another request')
            return existing[0]
        rows=self.execute(f'INSERT INTO jobs(project_id,created_by,idempotency_key,kind,raster_asset_id,prompt_id,aoi_id) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING {self.columns}',(project_id,self.user_id,data.idempotency_key,data.kind,data.raster_asset_id,data.prompt_id,data.aoi_id))
        if rows:
            return rows[0]
        rows=self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s AND created_by=%s AND idempotency_key=%s',(project_id,self.user_id,data.idempotency_key))
        if not rows or rows[0]['kind']!=data.kind or any(str(rows[0][key])!=str(getattr(data,key)) for key in ('raster_asset_id','prompt_id','aoi_id')):
            raise HTTPException(409,'Idempotency key conflicts with another request')
        return rows[0]

    def control(self,job_id,action):
        self.get(job_id)
        old=['failed'] if action=='retry' else ['queued','running']
        new='queued' if action=='retry' else 'cancelled'
        rows=self.execute(f'UPDATE jobs SET status=%s WHERE id=%s AND status=ANY(%s) RETURNING {self.columns}',(new,job_id,old))
        if not rows:
            raise HTTPException(409,'Job state or role does not allow this action')
        return rows[0]


def notify(job_id):
    try:
        with Redis.from_url(Settings().redis_url.get_secret_value(),socket_timeout=2,socket_connect_timeout=2) as redis:
            with redis.pipeline() as pipe:
                pipe.lpush('geoai:jobs:wake',str(job_id))
                pipe.ltrim('geoai:jobs:wake',0,9999)
                pipe.execute()
    except Exception:
        pass  # PostgreSQL queued rows are the durable queue; polling recovers missed hints.


router=APIRouter(tags=['jobs'])


@router.get('/projects/{project_id}/jobs')
def list_jobs(project_id: UUID,current: CurrentUser,offset: int = Query(default=0,ge=0,le=1000000)):
    accessible(project_id,current)
    return JobRepository(current.user['id']).list(project_id,offset)


@router.post('/projects/{project_id}/jobs',status_code=201)
def create_job(project_id: UUID,data: JobInput,current: CurrentUser):
    accessible(project_id,current)
    row=JobRepository(current.user['id']).create(project_id,data)
    notify(row['id'])
    return row


@router.get('/jobs/{job_id}')
def get_job(job_id: UUID,current: CurrentUser):
    return JobRepository(current.user['id']).get(job_id)


@router.post('/jobs/{job_id}/{action}')
def control_job(job_id: UUID,action: Literal['cancel','retry'],current: CurrentUser):
    row=JobRepository(current.user['id']).control(job_id,action)
    if action=='retry':
        notify(job_id)
    return row


@router.get('/models/available-endpoints')
def available_endpoints(current: CurrentUser):
    return UserSQLRepository(current.user['id']).execute('SELECT * FROM geoai_internal.available_model_endpoints()')

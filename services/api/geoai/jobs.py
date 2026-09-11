from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from redis import Redis
from .auth import CurrentUser
from .config import Settings
from .projects import accessible
from .spatial import UserSQLRepository


class JobInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['diagnostic'] = 'diagnostic'
    idempotency_key: UUID


class JobRepository(UserSQLRepository):
    columns = 'id,project_id,created_by,kind,status,progress,attempts,result,error_code,created_at,started_at,finished_at'

    def list(self,project_id):
        return self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s ORDER BY created_at DESC LIMIT 100',(project_id,))

    def get(self,job_id):
        rows=self.execute(f'SELECT {self.columns} FROM jobs WHERE id=%s',(job_id,))
        if not rows:
            raise HTTPException(404,'Job not found')
        return rows[0]

    def create(self,project_id,data):
        rows=self.execute(f'INSERT INTO jobs(project_id,created_by,idempotency_key,kind) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING {self.columns}',(project_id,self.user_id,data.idempotency_key,data.kind))
        if rows:
            return rows[0]
        rows=self.execute(f'SELECT {self.columns} FROM jobs WHERE project_id=%s AND created_by=%s AND idempotency_key=%s',(project_id,self.user_id,data.idempotency_key))
        if not rows or rows[0]['kind']!=data.kind:
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
def list_jobs(project_id: UUID,current: CurrentUser):
    accessible(project_id,current)
    return JobRepository(current.user['id']).list(project_id)


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

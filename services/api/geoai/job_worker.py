"""Internal job executor. Fencing prevents cancelled/stale attempts publishing results."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from .raster_worker import database
from .config import Settings
from .compute import MockComputeProvider
from .models import MockAdapter
from .worker_contract import ModelWorkerError


def claim_job(cfg):
    with database(cfg) as conn:
        conn.execute("UPDATE jobs SET status='failed',error_code='worker_interrupted',finished_at=now() WHERE status='running' AND started_at<now()-make_interval(secs=>%s)",(cfg.raster_timeout_seconds+30,))
        row=conn.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
        if row:
            row['claim_token']=uuid4()
            conn.execute("UPDATE jobs SET status='running',progress=10,attempts=attempts+1,claim_token=%s,started_at=now(),finished_at=NULL,error_code=NULL,result=NULL WHERE id=%s",(row['claim_token'],row['id']))
        return row


def fail_job(cfg,row,code):
    with database(cfg) as conn:
        conn.execute("UPDATE jobs SET status='failed',error_code=%s,finished_at=now() WHERE id=%s AND claim_token=%s AND status='running'",(code,row['id'],row['claim_token']))


def finish_job(cfg,row,result):
    with database(cfg) as conn:
        return conn.execute("UPDATE jobs SET status='succeeded',progress=100,result=%s,finished_at=now() WHERE id=%s AND claim_token=%s AND status='running' RETURNING id",(Jsonb(result),row['id'],row['claim_token'])).fetchone() is not None


def job_active(cfg,row):
    with database(cfg) as conn:
        return conn.execute("SELECT id FROM jobs WHERE id=%s AND claim_token=%s AND status='running'",(row['id'],row['claim_token'])).fetchone() is not None


def execute_job(row,workspace=None):
    cfg=Settings()
    try:
        if row['kind']=='geoextract_tile':
            from .tile_extraction import execute_tile
            execute_tile(cfg,row)
            return
        if row['kind']=='geoextract':
            from .extraction import execute_extraction
            execute_extraction(cfg,row)
            return
        if row['kind']!='diagnostic':
            raise ValueError('unsupported_job_kind')
        provider=MockComputeProvider(MockAdapter())
        output=provider.execute({'width':2,'height':2},{'support_mask':[1,0,0,1]})
        finish_job(cfg,row,{'mock':True,'model':'mock-v1','sample_count':len(output['probabilities'])})
    except ModelWorkerError as error:
        fail_job(cfg,row,error.code)
    except Exception:
        fail_job(cfg,row,'job_execution_failed')

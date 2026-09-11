"""Rollback-only local SQL acceptance against existing RLS and project schema."""
import json
from uuid import uuid4
from migrate import connection


def run():
    with connection() as conn:
        try:
            project=conn.execute("SELECT p.id,p.owner_id FROM projects p JOIN visual_prompts v ON v.project_id=p.id JOIN aois a ON a.project_id=p.id WHERE v.deleted_at IS NULL AND a.deleted_at IS NULL LIMIT 1").fetchone()
            assert project, 'Requires an existing project with AOI and Prompt'
            project_id,owner=project
            prompt=conn.execute('SELECT id,raster_asset_id FROM visual_prompts WHERE project_id=%s AND deleted_at IS NULL LIMIT 1',(project_id,)).fetchone()
            aoi=conn.execute('SELECT id FROM aois WHERE project_id=%s AND deleted_at IS NULL LIMIT 1',(project_id,)).fetchone()[0]
            conn.execute('SET LOCAL ROLE authenticated')
            conn.execute("SELECT set_config('request.jwt.claims',%s,true)",(json.dumps({'sub':str(owner),'role':'authenticated'}),))
            job=conn.execute("INSERT INTO jobs(project_id,created_by,idempotency_key,kind,raster_asset_id,prompt_id,aoi_id) VALUES (%s,%s,%s,'geoextract',%s,%s,%s) RETURNING id,execution_snapshot",(project_id,owner,uuid4(),prompt[1],prompt[0],aoi)).fetchone()
            assert job[1]['capture_basis']=='submission'
            frozen=job[1]
            conn.execute("UPDATE aois SET name=name||' test',deleted_at=now() WHERE id=%s",(aoi,))
            conn.execute("UPDATE visual_prompts SET name=name||' test',class_label='changed',deleted_at=now() WHERE id=%s",(prompt[0],))
            assert conn.execute('SELECT execution_snapshot FROM jobs WHERE id=%s',(job[0],)).fetchone()[0]==frozen
            assert conn.execute('SELECT count(*) FROM jobs WHERE id=%s',(job[0],)).fetchone()[0]==1
            conn.execute('SAVEPOINT denied')
            try:
                conn.execute("INSERT INTO jobs(project_id,created_by,idempotency_key,kind,raster_asset_id,prompt_id,aoi_id) VALUES (%s,%s,%s,'geoextract',%s,%s,%s)",(project_id,owner,uuid4(),prompt[1],prompt[0],aoi))
                raise AssertionError('Deleted resources accepted for a new job')
            except Exception as error:
                if isinstance(error,AssertionError):raise
                assert getattr(error,'sqlstate',None)=='23514'
                conn.execute('ROLLBACK TO SAVEPOINT denied')
            print('PASS: immutable submission snapshot, soft deletion preserves history, deleted inputs rejected')
        finally:
            conn.rollback()


if __name__=='__main__':run()

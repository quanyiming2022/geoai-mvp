"""Authenticated Agent acceptance against an isolated, caller-owned fixture.

Usage: python scripts/acceptance_workspace_agent.py STATE_JSON CREDENTIAL_ENV
Credentials stay local. Creates/removes two ordinary users and one temporary
membership. Never submits inference or changes model/worker configuration.
"""
import json,sys,uuid
from pathlib import Path
import httpx
from dotenv import dotenv_values
from migrate import ROOT

def run(state_path,credential_path):
    state=json.loads(Path(state_path).read_text());env=dotenv_values(ROOT/'.env');credentials=dotenv_values(credential_path)
    api='http://127.0.0.1:'+env['GEOAI_API_PORT'];created=[];member=None
    with httpx.Client(base_url=api,timeout=185,trust_env=False) as client,httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':env['SERVICE_ROLE_KEY'],'Authorization':'Bearer '+env['SERVICE_ROLE_KEY']},timeout=30,trust_env=False) as admin:
        def login(email,password):return {'Authorization':'Bearer '+client.post('/auth/login',json={'email':email,'password':password}).raise_for_status().json()['access_token']}
        owner=login(credentials['EMAIL'],credentials['PASSWORD']);project=state['project'];base=f'/projects/{project}'
        try:
            headers=[]
            for _ in range(2):
                seed=uuid.uuid4().hex;email=seed+'@example.test';password=seed+'Aa1!'
                created.append(admin.post('/auth/v1/admin/users',json={'email':email,'password':password,'email_confirm':True}).raise_for_status().json()['id']);headers.append(login(email,password))
            member=created[0];client.post(base+'/members',headers=owner,json={'user_id':member,'role':'viewer'}).raise_for_status()
            context={'channel':'worker','raster_id':state['asset']['id'],'prompt_id':state['prompt']['id'],'aoi_id':state['aoi']['id'],'window_aoi_id':state['aoi']['id'],'query_col':728,'query_row':716}
            resolved=client.post(base+'/assistant/context',headers=owner,json=context).raise_for_status().json()
            required='project current_raster selected_aoi selected_visual_prompt selected_result current_map_center current_map_bounds current_zoom visible_layers active_left_panel recent_jobs available_models enabled_compute_endpoints endpoint_health model_usage_policy current_user_role available_aois available_visual_prompts available_rasters'.split()
            assert all(k in resolved for k in required) and resolved['current_user_role']=='owner'
            payload={'text':'用这个样例测试这里','workspace_context':context}
            denied=client.post(base+'/assistant/agent',headers=headers[0],json=payload).raise_for_status().json();assert denied['kind']=='explanation' and 'draft_id' not in denied
            assert client.post(base+'/assistant/agent',headers=headers[1],json=payload).status_code==404
            assert client.post(base+'/assistant/context',headers=headers[1],json=context).status_code==404
            assert client.post(base+'/assistant/agent',headers=owner,json={**payload,'workspace_context':{**context,'raster_id':str(uuid.uuid4())}}).status_code in (404,422)
            draft=client.post(base+'/assistant/agent',headers=owner,json=payload).raise_for_status().json();assert draft['kind']=='draft'
            assert client.post(base+'/assistant/confirm',headers=headers[0],json={'draft_id':draft['draft_id'],'confirmed':True}).status_code==403
            job=client.get(base+'/jobs',headers=owner).raise_for_status().json()[0]
            status=client.post(base+'/assistant/agent',headers=headers[0],json={'text':'刚才任务怎么样？','workspace_context':{**context,'last_job':job['id']}}).raise_for_status().json();assert status['job']['id']==job['id']
            assert client.post(base+'/assistant/observe',headers=headers[1],json={'job_id':job['id']}).status_code==404
            assert client.post(base+'/assistant/cancel',headers=owner,json={'confirmation_id':str(uuid.uuid4()),'confirmed':True}).status_code==410
            print('PASS: authenticated unified context, owner draft only, viewer read-only, outsider denied, foreign resource denied, confirmation ownership, recent job and missing cancellation confirmation')
        finally:
            if member:client.delete(base+'/members/'+member,headers=owner).raise_for_status()
            for uid in created:admin.delete('/auth/v1/admin/users/'+uid).raise_for_status()

if __name__=='__main__':run(*sys.argv[1:])

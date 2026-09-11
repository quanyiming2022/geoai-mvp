"""Real local project settings authorization and email membership acceptance."""
import uuid
import httpx
from dotenv import dotenv_values
from migrate import ROOT


def run():
    env=dotenv_values(ROOT/'.env')
    base='http://127.0.0.1:'+env['GEOAI_API_PORT']
    key=env['SERVICE_ROLE_KEY']
    ids=[]
    with httpx.Client(base_url=env['SUPABASE_PUBLIC_URL'],headers={'apikey':key,'Authorization':'Bearer '+key},timeout=30) as auth, httpx.Client(base_url=base,timeout=30) as api:
        try:
            users=[]
            for _ in range(4):
                seed=uuid.uuid4().hex
                credentials={'email':seed+'@example.test','password':seed+'Aa1!'}
                user=auth.post('/auth/v1/admin/users',json={**credentials,'email_confirm':True}).raise_for_status().json()
                ids.append(user['id'])
                token=api.post('/auth/login',json=credentials).raise_for_status().json()['access_token']
                users.append((credentials['email'],{'Authorization':'Bearer '+token},token))
            owner,editor,viewer,outsider=users
            project=api.post('/projects',headers=owner[1],json={'name':'Settings acceptance'}).raise_for_status().json()
            path='/projects/'+project['id']
            assert api.patch(path,headers=owner[1],json={'name':'Updated settings','description':'Verified'}).status_code==200
            for user,role in [(editor,'editor'),(viewer,'viewer')]:
                assert api.post(path+'/members/by-email',headers=owner[1],json={'email':user[0].upper(),'role':role}).status_code==201
            listing=api.get(path+'/member-identities',headers=owner[1]).raise_for_status().json()
            assert {m['email'] for m in listing}=={owner[0],editor[0],viewer[0]}
            for user in [editor,viewer]:
                assert api.get(path,headers=user[1]).status_code==200
                assert api.post(path+'/members/by-email',headers=user[1],json={'email':outsider[0],'role':'editor'}).status_code==403
                assert api.patch(path+'/members/'+ids[2],headers=user[1],json={'role':'editor'}).status_code==403
                assert api.delete(path+'/members/'+ids[2],headers=user[1]).status_code==403
                # Bypass FastAPI: current PostgREST RLS must independently refuse membership writes.
                direct=auth.post('/rest/v1/project_members',headers={'apikey':env['ANON_KEY'],'Authorization':'Bearer '+user[2]},json={'project_id':project['id'],'user_id':ids[3],'role':'viewer'})
                assert direct.status_code>=400
            assert api.patch(path,headers=viewer[1],json={'name':'Denied'}).status_code==403
            assert api.get(path,headers=outsider[1]).status_code==404
            assert api.get(path+'/member-identities',headers=outsider[1]).status_code==404
            assert api.post(path+'/members/by-email',headers=outsider[1],json={'email':owner[0],'role':'viewer'}).status_code==404
            assert api.post(path+'/members/by-email',headers=owner[1],json={'email':'missing-'+uuid.uuid4().hex+'@example.test','role':'viewer'}).status_code==404
            assert api.post(path+'/members/by-email',headers=owner[1],json={'email':outsider[0],'role':'admin'}).status_code==422
            assert api.patch(path+'/members/'+ids[1],headers=owner[1],json={'role':'viewer'}).status_code==200
            assert api.patch(path,headers=editor[1],json={'name':'Denied after downgrade'}).status_code==403
            assert api.delete(path+'/members/'+ids[1],headers=owner[1]).status_code==204
            assert api.get(path,headers=editor[1]).status_code==404
            print('PASS: email add/list, owner update/change/remove, editor/viewer denied membership writes, viewer read-only, outsider denied, direct PostgREST RLS, unsupported admin rejected')
        finally:
            for uid in reversed(ids):
                auth.delete('/auth/v1/admin/users/'+uid).raise_for_status()

if __name__=='__main__':
    try:
        run()
    except Exception as error:
        print('FAIL: '+type(error).__name__+' (secrets suppressed)')
        raise SystemExit(1) from None

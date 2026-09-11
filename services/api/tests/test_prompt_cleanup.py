from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from geoai import prompts


@pytest.mark.parametrize('failure,remaining', [('put',0),('denied',0),('uncertain',2)])
def test_failed_prompt_compensation(monkeypatch,failure,remaining):
    project,asset=uuid4(),uuid4()
    stored={}
    class Storage:
        def create_signed_url(self,*args):
            return 'local-source'
        def put_object(self,bucket,key,blob,mime):
            stored[key]=blob
            if failure=='put' and key.endswith('mask.tif'):
                raise httpx.ConnectError('interrupted')
        def delete_object(self,bucket,key):
            stored.pop(key,None)
        def close(self):
            pass
    class Repo:
        def __init__(self,*args):
            pass
        def validate(self,*args):
            pass
        def create(self,*args):
            raise HTTPException(403 if failure=='denied' else 503,'failure')
    monkeypatch.setattr(prompts,'accessible',lambda *a:None)
    monkeypatch.setattr(prompts,'asset_for_user',lambda *a:({'project_id':str(project),'id':str(asset),'cog_object_key':f'{project}/rasters/{asset}/cog.tif'},SimpleNamespace(storage_bucket='geoai')))
    monkeypatch.setattr(prompts,'PromptRepository',Repo)
    monkeypatch.setattr(prompts,'provider',lambda *a,**kw:Storage())
    monkeypatch.setattr(prompts,'support_crop',lambda *a:(b'image',b'mask','EPSG:4326'))
    data=prompts.PromptInput(name='test',raster_asset_id=asset,geometry={'type':'Polygon','coordinates':[[[0,0],[1,0],[0,1],[0,0]]]})
    with pytest.raises(HTTPException):
        prompts.create_prompt(project,data,SimpleNamespace(user={'id':str(uuid4())}))
    assert len(stored)==remaining

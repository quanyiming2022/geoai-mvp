import pytest
from fastapi import HTTPException
from geoai import prompts


def test_failed_prompt_mask_upload_keeps_original_version_and_cleans_staging():
    assert hasattr(prompts,'publish_prompt_revision'), 'Versioned prompt publication is missing'
    class Storage:
        def __init__(self):self.objects={'original/image.tif':b'old image','original/mask.tif':b'old mask'}
        def put_object(self,bucket,key,blob,mime):
            if key.endswith('/mask.tif'):raise ValueError('injected mask upload failure')
            self.objects[key]=blob
        def delete_object(self,bucket,key):self.objects.pop(key,None)
    storage=Storage()
    def commit(*args):raise AssertionError('Cannot commit incomplete artifacts')
    with pytest.raises(ValueError):
        prompts.publish_prompt_revision(storage,'bucket','project/prompts/id/versions/new',b'new image',b'new mask',commit)
    assert storage.objects=={'original/image.tif':b'old image','original/mask.tif':b'old mask'}


def test_uncertain_prompt_commit_retains_new_objects_for_recovery():
    assert hasattr(prompts,'publish_prompt_revision')
    class Storage:
        def __init__(self):self.objects={}
        def put_object(self,bucket,key,blob,mime):self.objects[key]=blob
        def delete_object(self,bucket,key):self.objects.pop(key,None)
    storage=Storage()
    def commit(*args):raise HTTPException(503,'uncertain database outcome')
    with pytest.raises(HTTPException):
        prompts.publish_prompt_revision(storage,'bucket','p/prompts/id/versions/new',b'image',b'mask',commit)
    assert len(storage.objects)==2


def test_concurrent_prompt_revision_conflict_cleans_only_unpublished_objects():
    class Storage:
        def __init__(self):self.objects={'current/image.tif':b'current','current/mask.tif':b'current'}
        def put_object(self,bucket,key,blob,mime):self.objects[key]=blob
        def delete_object(self,bucket,key):self.objects.pop(key,None)
    storage=Storage()
    def commit():raise HTTPException(409,'Revision conflict')
    with pytest.raises(HTTPException) as error:
        prompts.publish_prompt_revision(storage,'bucket','p/prompts/id/versions/stale',b'image',b'mask',commit)
    assert error.value.status_code==409
    assert storage.objects=={'current/image.tif':b'current','current/mask.tif':b'current'}

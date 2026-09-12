import asyncio
import pytest
from fastapi import HTTPException
from geoai.assistant_cancellation import checker,cancellable
from geoai.workspace_agent import cancellation_key


def test_cancellation_closes_running_provider_coroutine():
    closed=[];cancel=[False]
    async def provider():
        try:await asyncio.sleep(20)
        finally:closed.append(True)
    async def run():
        async def trigger():await asyncio.sleep(.02);cancel[0]=True
        token=checker.set(lambda:cancel[0])
        try:
            task=asyncio.create_task(trigger())
            with pytest.raises(HTTPException) as error:await asyncio.wait_for(cancellable(provider()),1)
            assert error.value.detail['code']=='ASSISTANT_CANCELLED'
            await task
        finally:checker.reset(token)
    asyncio.run(run());assert closed==[True]


def test_cancellation_is_owner_and_project_scoped():
    assert cancellation_key('p','u','r')!=cancellation_key('q','u','r')
    assert cancellation_key('p','u','r')!=cancellation_key('p','v','r')

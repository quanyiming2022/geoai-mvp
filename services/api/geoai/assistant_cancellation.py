"""Per-request cancellation; scope derives from authenticated user/project."""
import asyncio
from contextvars import ContextVar
from fastapi import HTTPException

checker=ContextVar('assistant_cancel_checker',default=None)

def check_cancelled():
    check=checker.get()
    if check and check():raise HTTPException(409,{'code':'ASSISTANT_CANCELLED','message':'已停止本次请求。'})

async def cancellable(awaitable):
    check=checker.get()
    if not check:return await awaitable
    async def monitor():
        while True:
            if await asyncio.to_thread(check):raise HTTPException(409,{'code':'ASSISTANT_CANCELLED','message':'已停止本次请求。'})
            await asyncio.sleep(.15)
    task=asyncio.create_task(awaitable);watch=asyncio.create_task(monitor())
    try:
        done,_=await asyncio.wait([task,watch],return_when=asyncio.FIRST_COMPLETED)
        if watch in done:return await watch
        return await task
    finally:
        task.cancel();watch.cancel()
        await asyncio.gather(task,watch,return_exceptions=True)

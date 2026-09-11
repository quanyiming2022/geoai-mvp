from uuid import uuid4
import pytest
from pydantic import ValidationError
from geoai.jobs import JobInput, notify


def test_job_rejects_unknown_kind_and_client_status():
    with pytest.raises(ValidationError):
        JobInput(idempotency_key=uuid4(),kind='run-shell')
    with pytest.raises(ValidationError):
        JobInput(idempotency_key=uuid4(),status='succeeded')


def test_redis_hint_failure_does_not_lose_durable_job(monkeypatch):
    monkeypatch.setattr('geoai.jobs.Settings',lambda: (_ for _ in ()).throw(ConnectionError()))
    notify(uuid4())


def test_process_start_failure_releases_slot_and_directory(monkeypatch):
    from geoai.worker import ProcessSlot
    paths=[]
    class Child:
        pid=None
        def start(self):
            raise OSError('process limit')
    class Context:
        def Process(self,target,args):
            paths.append(args[1])
            return Child()
    monkeypatch.setattr('geoai.worker.multiprocessing.get_context',lambda *a:Context())
    slot=ProcessSlot(lambda:None,'geoai-test-')
    assert slot.start({'id':'test'}) is False
    assert slot.process is None and slot.local_check(1) is None
    from pathlib import Path
    assert all(not Path(p).exists() for p in paths)


def test_local_deadline_cleanup_needs_no_database(monkeypatch,tmp_path):
    from geoai.worker import ProcessSlot
    class Child:
        def is_alive(self):
            return True
    class Scratch:
        def cleanup(self):
            pass
    stopped=[]
    monkeypatch.setattr('geoai.worker.stop_process',lambda child:stopped.append(child))
    slot=ProcessSlot(None,'test-')
    slot.process=Child()
    slot.row={'id':'test'}
    slot.scratch=Scratch()
    slot.started=-1000
    assert slot.local_check(1)==({'id':'test'},'processing_timeout')
    assert len(stopped)==1 and slot.process is None

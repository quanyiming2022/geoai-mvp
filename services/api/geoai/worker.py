import logging
import multiprocessing
import tempfile
import time
import rasterio
from redis import Redis
from .config import Settings
from .raster_worker import claim, process, fail
from .job_worker import claim_job, execute_job, fail_job, job_active

logging.basicConfig(level=logging.INFO)


def stop_process(active):
    active.terminate()
    active.join(3)
    if active.is_alive():
        active.kill()
        active.join(3)


def supervise(active, row, scratch, started, cfg):
    if not active.is_alive():
        active.join()
        scratch.cleanup()
        fail(cfg, row, "worker_process_failed")
        return False
    if time.monotonic() - started > cfg.raster_timeout_seconds:
        stop_process(active)
        scratch.cleanup()
        fail(cfg, row, "processing_timeout")
        return False
    return True


def heartbeat(redis):
    try:
        redis.set("geoai:raster:heartbeat", rasterio.__gdal_version__, ex=30)
    except Exception as error:
        logging.error("Worker heartbeat: %s", type(error).__name__)


class ProcessSlot:
    """Own process lifetime independently of all database/network reporting."""
    def __init__(self, target, prefix):
        self.target, self.prefix = target, prefix
        self.process = self.row = self.scratch = None
        self.started = 0

    def start(self, row):
        scratch = tempfile.TemporaryDirectory(prefix=self.prefix)
        child = None
        try:
            child = multiprocessing.get_context('spawn').Process(target=self.target,args=(row,scratch.name))
            child.start()
        except Exception:
            if child is not None and child.pid is not None:
                stop_process(child)
            scratch.cleanup()
            return False
        self.process, self.row, self.scratch = child, row, scratch
        self.started = time.monotonic()
        return True

    def clear(self):
        row = self.row
        self.process = self.row = None
        scratch, self.scratch = self.scratch, None
        scratch.cleanup()
        return row

    def stop(self):
        stop_process(self.process)
        return self.clear()

    def local_check(self, timeout):
        if self.process is None:
            return None
        if not self.process.is_alive():
            self.process.join()
            return self.clear(), 'worker_process_failed'
        if time.monotonic()-self.started > timeout:
            return self.stop(), 'processing_timeout'
        return None


def main():
    cfg = Settings()
    redis = Redis.from_url(cfg.redis_url.get_secret_value(),socket_timeout=2,socket_connect_timeout=2)
    with rasterio.Env() as env:
        if 'COG' not in env.drivers():
            raise RuntimeError('GDAL COG driver unavailable')
    raster = ProcessSlot(process,'geoai-raster-')
    job = ProcessSlot(execute_job,'geoai-job-')
    slots = [(raster,claim,fail),(job,claim_job,fail_job)]
    while True:
        # Check BOTH local deadlines before any remote I/O, even if DB is unavailable.
        reports = []
        for slot, _, reporter in slots:
            event = slot.local_check(cfg.raster_timeout_seconds)
            if event:
                reports.append((reporter,*event))
        for reporter,row,code in reports:
            try:
                reporter(cfg,row,code)
            except Exception as error:
                logging.error('Worker report: %s',type(error).__name__)
        heartbeat(redis)
        if job.process:
            try:
                if not job_active(cfg,job.row):
                    job.stop()
            except Exception as error:
                logging.error('Job cancellation check: %s',type(error).__name__)
        for slot,claimer,reporter in slots:
            if slot.process is not None:
                continue
            try:
                row = claimer(cfg)
                if row and not slot.start(row):
                    reporter(cfg,row,'worker_start_failed')
            except Exception as error:
                logging.error('Worker claim/start: %s',type(error).__name__)
        try:
            redis.rpop('geoai:jobs:wake')
        except Exception:
            pass
        time.sleep(2)


if __name__ == "__main__":
    main()

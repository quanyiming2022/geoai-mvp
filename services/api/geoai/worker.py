import logging
import multiprocessing
import tempfile
import time
import rasterio
from redis import Redis
from .config import Settings
from .raster_worker import claim, process, fail

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


def main():
    cfg = Settings()
    redis = Redis.from_url(
        cfg.redis_url.get_secret_value(), socket_timeout=5, socket_connect_timeout=5
    )
    with rasterio.Env() as env:
        if "COG" not in env.drivers():
            raise RuntimeError("GDAL COG driver unavailable")
    active = None
    row = None
    scratch = None
    started = 0
    while True:
        heartbeat(redis)
        try:
            if active and not supervise(active, row, scratch, started, cfg):
                active = None
            if active is None:
                row = claim(cfg)
                if row:
                    scratch = tempfile.TemporaryDirectory(prefix="geoai-raster-")
                    active = multiprocessing.get_context("spawn").Process(
                        target=process, args=(row, scratch.name)
                    )
                    active.start()
                    started = time.monotonic()
        except Exception as error:
            logging.error("Worker cycle: %s", type(error).__name__)
        time.sleep(2)


if __name__ == "__main__":
    main()

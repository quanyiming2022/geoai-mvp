"""P0 raster runtime probe; no processing queue is claimed until P4/P7."""

import logging
import time
import rasterio
from redis import Redis
from .config import Settings

logging.basicConfig(level=logging.INFO)


def main():
    cfg = Settings()
    redis = Redis.from_url(
        cfg.redis_url.get_secret_value(), socket_timeout=5, socket_connect_timeout=5
    )
    with rasterio.Env() as env:
        if "COG" not in env.drivers():
            raise RuntimeError("GDAL COG driver unavailable")
    while True:
        try:
            redis.set("geoai:raster:heartbeat", rasterio.__gdal_version__, ex=30)
        except Exception as exc:
            logging.error("Raster heartbeat failed: %s", type(exc).__name__)
        time.sleep(10)


if __name__ == "__main__":
    main()

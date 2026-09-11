"""Internal bounded health polling; never changes endpoint configuration/enabled."""
import logging
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from psycopg.types.json import Jsonb
from .config import Settings
from .raster_worker import database
from .endpoints import probe_endpoint

logger = logging.getLogger(__name__)


def refresh_endpoint(endpoint):
    # Start time fences a slow older response against a newer completed check.
    started = datetime.now(timezone.utc)
    status, code, info = probe_endpoint(endpoint)
    with database(Settings()) as conn:
        row = conn.execute("""UPDATE geoai_internal.model_endpoints
            SET health_status=%s,health_code=%s,model_info=%s,last_checked_at=%s,
                last_healthy_at=CASE WHEN %s='healthy' THEN %s ELSE last_healthy_at END
            WHERE id=%s AND config_revision=%s
              AND (last_checked_at IS NULL OR last_checked_at<=%s) RETURNING id""",
            (status,code,Jsonb(info),started,status,started,endpoint['id'],endpoint['config_revision'],started)).fetchone()
    return status if row else 'stale'


def endpoint_rows(endpoint_id=None):
    with database(Settings()) as conn:
        return conn.execute("""SELECT e.*,r.checkpoint_digest,r.model_name,r.model_version
            FROM geoai_internal.model_endpoints e JOIN geoai_internal.model_releases r
            ON r.id=e.model_release_id WHERE e.enabled AND e.provider_type='lan_http'"""
            + (' AND e.id=%s' if endpoint_id else ''), (endpoint_id,) if endpoint_id else ()).fetchall()


def require_live_endpoint(endpoint_id, revision):
    from fastapi import HTTPException
    rows = endpoint_rows(endpoint_id)
    if not rows or rows[0]['config_revision'] != revision:
        raise HTTPException(422, 'Compute configuration changed or disabled')
    if refresh_endpoint(rows[0]) != 'healthy':
        raise HTTPException(409, 'Compute endpoint unavailable; reconnect before submitting')


def monitor(stop):
    while not stop.is_set():
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(refresh_endpoint, endpoint_rows()))
        except Exception:
            logger.warning('Endpoint health refresh unavailable')
        stop.wait(10)

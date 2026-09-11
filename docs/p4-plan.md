# P4 Raster Worker and COG

Worker claims uploaded raster rows using PostgreSQL FOR UPDATE SKIP LOCKED; durable DB status is authoritative. Redis heartbeat remains live while a bounded child process performs raster work. Claim tokens prevent stale workers overwriting newer results; timeout/crash marks failed. Restart recovers stale processing claims. No inference jobs until P7.

Stream object to disk via ObjectStorageProvider, verify source checksum, inspect CRS/dimensions/bands/dtype/nodata/resolution, convert to tiled COG, create PNG thumbnail, store derived objects, record WGS84 footprint (PostGIS) and bounds. Preserve source CRS and original bytes. Processing memory uses GDAL windows/streamed conversion, maximum pixels and timeout configurable.

Authenticated raster tile endpoint opens a short-lived internal signed COG URL for range reads and reprojects each XYZ window to Web Mercator. Next streams PNG to browser with caller identity. Workspace polls pending raster status, loads ready raster source, fits bounds and shows processing/error metadata. All object access stays project-scoped.

Acceptance: synthetic real source -> worker -> COG layout/metadata/PostGIS footprint -> range 206 -> nonempty PNG tile, outside tile transparent, cross-user denial, restart persistence, build/static/unit/Docker and browser correctly located raster. Commit/push then P5.

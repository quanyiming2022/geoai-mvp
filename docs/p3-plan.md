# P3 Raster Asset Upload

Raw GeoTIFF upload streams through a same-origin Next route to FastAPI, using caller bearer authentication. FastAPI checks owner/editor role before reading, bounds streamed bytes, spools to disk, validates TIFF signature/GTiff driver/CRS, computes SHA256, and stores via ObjectStorageProvider. Metadata row is written through a user-scoped RasterRepository; insertion failure compensates only the newly generated object. No raster pixels in PostgreSQL.

raster_assets uses project RLS, immutable identity/object path, size/checksum/upload status. Paths are project UUID + asset UUID namespaces. Download signs only the canonical key in the configured private bucket after verifying project membership. Direct client metadata cannot redirect signing to unrelated objects. Viewer can list/download, never upload. Conversion/metadata extraction belongs to P4.

UI: workspace asset list, owner/editor file input with progress and error feedback; viewers read-only. Same-origin upload checks Origin before streaming. No arbitrary backend proxy routes or remote URL imports.

Acceptance: malformed/non-georeferenced TIFF rejection, size bound, actual upload/read/checksum/storage metadata, cross-project and viewer denial via API and direct RLS, build/static/unit/Docker, browser file upload and visible asset. Commit/push then P4.

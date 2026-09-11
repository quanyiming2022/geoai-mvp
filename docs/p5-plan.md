# P5 Layers and AOI

Add raster visibility/opacity and polygon/rectangle drawing to the existing MapLibre workspace. Drawing is temporary until an editor saves an AOI. Viewer remains read-only. Saved AOIs are listed and rendered from database geometry.

Store EPSG:4326 Polygon in PostGIS with validity/coordinate bounds/area checks, project ownership/membership RLS and explicit grants. User-scoped SQL repository drops to authenticated role and sets only the verified Auth subject before querying spatial functions. UI accesses FastAPI through server actions, never SQL or Supabase directly.

Acceptance: draw helper tests, real SQL geometry/area and self-intersection rejection, owner/editor save, viewer and other project denial, refresh persistence, local build/static/unit/Docker and browser draw/save/render/opacity controls. Commit/push before P6.

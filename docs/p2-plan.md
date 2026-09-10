# P2 Project Workspace and MapLibre

Add an authenticated workspace route per project. Keep existing project settings/member management. Load MapLibre only in a client effect, remove the map and observers on unmount, report initialization/rendering failures.

Default style is entirely local: background plus a generated WGS84 graticule, no remote tiles, glyphs or sprites. Display zoom and longitude/latitude; allow zoom controls, keyboard navigation and reset view. This is a coordinate canvas, not a street basemap. Upload and raster rendering begin in P3/P4.

Acceptance: static/build/unit checks; live authenticated workspace and cross-user denial; local Docker health; browser canvas load, zoom change, reset, project navigation. Commit and push only after verification.

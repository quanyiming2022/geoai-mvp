# v0.2.0-p9c.4 — Workspace selection and AOI preflight

This P9C correctness release keeps P8/P9 execution behavior and the frozen
SkySense++ integration unchanged.

- Workspace entry starts with no selected raster or spatial object. Persistent
  map position and layer presentation remain available, while transient object
  selection is no longer restored.
- Mock and real extraction workflows start with `请选择 AOI`; the real workflow
  also requires an explicit target raster unless a confirmed assistant context
  supplies one.
- AOIs created from the extraction workflow or assistant are checked against
  the authoritative COG geotransform before insertion. An AOI outside the
  target raster or larger than the current 512 × 512 single-window capability
  remains an unsaved draft and can be redrawn.
- The geometry preflight is read-only and uses project authorization. Ordinary
  AOI creation outside an extraction task remains available for project data
  management.

Local verification: Web tests 15 PASS, API tests 155 PASS, typecheck/lint PASS,
production Docker build PASS, isolated browser acceptance PASS, P8 full
acceptance PASS, P9 native tile and synthetic HTTP PASS, and P9C local LLM
draft/confirmation acceptance PASS. The isolated browser fixture was removed
after verification.

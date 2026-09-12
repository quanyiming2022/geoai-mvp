# v0.2.0-p9c.3 — Assistant and Mock workflow correctness

This release is a P9C Workspace hardening patch. It does not change the frozen
SkySense++ adapter, native 512×512 inference contract, P8 execution behavior,
or the P10 capability evidence already recorded on the branch.

## Corrected behavior

- An active assistant task is scoped to the current Workspace visit. Closing
  the extraction workflow or leaving and returning starts a clean task; users
  may still archive conversations explicitly and delete individual archives.
- AOI or Visual Prompt creation resumes the pending assistant task using the
  resource that was just saved.
- Mock GeoExtract again offers AOI creation, selects the newly created AOI, and
  reports submission success or failure directly in the workflow.
- An AOI drawn from the assistant or extraction workflow is checked against the
  target raster before persistence. An out-of-bounds draft remains unsaved and
  must be redrawn.
- Oversized AOIs report their source-pixel dimensions and only offer alternate
  AOIs that the selected raster can actually analyze in one native window.

## Local validation

- Web tests: 14 PASS; typecheck, lint and Docker production build PASS.
- FastAPI tests: 154 PASS.
- Browser: active-session reset, one minimize control, AOI continuation, Mock
  submission feedback, out-of-bounds pre-save rejection, history deletion and
  clean re-entry PASS.
- Existing small/large AOI workflow browser regressions PASS at 1440×900 and
  1920×1080.
- P8 full acceptance, P9 native-window and synthetic HTTP/cancellation, and P9C
  local LLM → confirm → Mock regressions PASS.

The temporary browser account, project, raster and AOIs were cleaned after the
acceptance run; no user project data was modified.

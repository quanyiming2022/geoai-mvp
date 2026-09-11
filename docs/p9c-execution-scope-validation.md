# P9C execution scope correctness

Baseline: `4533a79`. No model adapter, preprocessing, probability, threshold, database or Job API changes.

- Assistant schema distinguishes `single_tile` and `full_aoi`. Explicit whole-area language takes precedence over any existing window. Unsupported scope returns `CAPABILITY_NOT_AVAILABLE` with resolved resource labels and no executable draft.
- AOI stays in worker context. Full-area rejection does not ask for pixel coordinates or silently select a tile.
- Assistant and manual single-tile form use map selection. A read-only authenticated endpoint converts a WGS84 map click through the source CRS/affine transform into a bounded 512×512 native window. Pixel coordinates remain internal hidden contract fields.
- A user must explicitly choose the offered single-tile alternative, select a map position, generate a new draft and confirm execution.
- Existing explicit Mock diagnostic requests remain bounded synthetic previews, never advertised as full-area inference.

Validation: backend 99 tests, frontend 5 tests, typecheck/lint and Docker production build PASS. Original P8, P9 native-tile and P9 HTTP acceptance PASS. Real local Qwen draft → confirmation → Mock Job → review/export acceptance PASS. Two obsolete P9C test expectations were updated to match baseline resource revisions and authorized geometry editing; geometry-preservation and viewer-denial assertions remain.

Actual browser: worker AOI context automatically populated with `12aoi`; original user phrase rejected with capability message; explicit alternative collapsed the panel, map click selected the window, then Qwen produced a draft showing Raster/AOI/Prompt/Model/Scope/Capability with no pixel inputs. No job was created by the rejection or draft generation. Local screenshots: `artifacts/p9c-full-aoi-blocked.png`, `artifacts/p9c-single-tile-draft.png`.

P10/P11 not started. Subsequent user request is Workspace Agent v1, preserving this capability boundary.

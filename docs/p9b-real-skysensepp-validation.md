# P9B real SkySense++ validation

Validation: 2026-09-11–12. Local macOS arm64 platform, LAN Linux RTX 4090 Worker.

## Conclusions

| Gate | Result |
|---|---|
| P9B Engineering Integration | PASS: real HTTP inference, native pixels, PostGIS, map selection, offline/recovery and new post-recovery job |
| Same-image | PASS (conditioning sanity check only) |
| Same-class different-tile | WEAK |
| Unrelated-query rejection | FAIL: significant agricultural false positives |
| Building extraction capability | **NOT PASSED** |

Engineering PASS does not certify building extraction accuracy or production readiness. Real-result review/export evidence and resource-maintenance regressions are recorded separately below; they are not inferred from model health. No P11 work is authorized by this report.

## Frozen identity and input

- Model: SkySense++ / research-v1 / research_only.
- Official source: cb0c6b774471ad3314354041c8fa6aae7d49a9bb.
- Checkpoint SHA256: 32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c.
- Seed 42; foreground slot 24; RTX 4090, CUDA 12.1.
- Approved prompt: 建筑-基准01, SPOT6 1 m RGB, source-resolution support/query tiles.
- A query window: col 730, row 715, 512×512. B: col 0, row 768. C: col 256, row 0. D uses the exact B query with vegetation support.
- B is same-scene, non-overlapping cross-tile, **not** an independent cross-image generalization test.
- Freeze preprocessing, mask normalization, slot binding and query-half extraction. New changes require reproducible evidence of divergence from the official path.

## Engineering evidence

The platform result for job `414c60b4-bb14-443f-9a76-0cb11d1c3aba` is pixel-identical to the independent A probability raster after preserving full geometry precision in SQL GeoJSON serialization. PostGIS geometry validity and MapLibre display/selection were verified. That serialization fix does not change the model adapter.

On September 11 the actual Worker was stopped after confirming there were no queued/running real jobs. The new internal monitor automatically recorded `offline / endpoint_unreachable`; Workspace disabled real extraction, while `/health/ready` remained HTTP 200 and existing successful jobs remained intact. Submission preflight rejected the disconnected endpoint with HTTP 409.

Worker restart restored health automatically, without enabling a disabled endpoint or editing database configuration. The same open Workspace automatically re-enabled real extraction. A new browser-submitted job `124aee3c-afca-42a1-9741-82a3386951bc` succeeded: 3 polygons, 2756 foreground pixels, 549.44 ms Worker runtime, matching baseline input digests and probability statistics.

Monitoring runs every 10 seconds with bounded HTTP health calls; Workspace and resource pages refresh every 10 seconds. Status is periodically observed, not instantaneous. Submission also performs a fresh health/identity check. A disconnect after admission remains an ordinary fenced durable-job failure, never success. Disabled nodes remain disabled and support explicit administrator diagnostics only.

## Capability measurements

Foreground percentages derived from the **same frozen probabilities**:

| Case | Mean | Std | ≥0.3 | ≥0.5 | ≥0.7 | Warm runtime ms |
|---|---:|---:|---:|---:|---:|---:|
| A same-image | .07345 | .09924 | 2.911% | 1.051% | .235% | 249.55 |
| B different building tile | .08103 | .08034 | 1.853% | .082% | 0% | 246.10 |
| C unrelated query | .14036 | .16145 | 13.554% | 6.061% | .0019% | 244.22 |
| D wrong prompt, B query | .35360 | .19202 | 62.362% | 31.813% | .372% | 245.55 |

Peak allocated GPU memory: 12,059,968,000 bytes (11.23 GiB), not total device VRAM. Runtime excludes startup, HTTP transport and GIS processing. No held-out ground truth exists; no held-out IoU/F1 is claimed.

B versus D: mean probability delta (D−B) .27257; mean absolute delta .28337. At 0.5, foreground changes by +31.731 percentage points and 31.895% of pixels change binary classification. Prompt choice clearly changes output, but this alone does not establish correct semantic control.

C's false positives cannot be declared solved by choosing threshold 0.7: that also removes all B detections. Thresholds are diagnostic comparisons only; building capability remains NOT PASSED.

## Preserved local artifacts

Private imagery/weights remain outside Git. Paths relative to the repository:

- `artifacts/p9b-building/registered-run/`: all original A/B/C/D inputs, probabilities, masks, overlays and metrics.
- `artifacts/p9b-building/threshold-analysis-20260911/`: separate 0.3/0.5/0.7 masks/overlays, quantiles, probability hashes and B/D spatial delta. Original artifacts were not overwritten.
- `artifacts/p9b-building/platform-job-fixed/`: pixel-equality evidence.
- `artifacts/p9b-building/input-audit.json`: previously completed official-path audit; not rerun for this task.

Analysis is reproducible with `scripts/gpu/analyze-building-baseline.py INPUT NEW_OUTPUT_DIRECTORY`; existing output directories are refused.

## Review, export and maintenance acceptance

The user explicitly authorized review of recovery job `124aee3c-afca-42a1-9741-82a3386951bc` for acceptance only. Through the real administrator browser, candidate #2 (`6169ef92-69b3-4673-99e3-6b575040760f`, approximately 666 m²) was accepted and candidate #3 (`f0e3a431-b6b4-46a6-be00-0259a833ebd4`) rejected. Audit rows were verified. The accepted-export control was exercised; a separate read-only GeoJSON evidence copy and audit record are stored as `artifacts/p9b-building/real-reviewed-accepted.geojson` and `real-review-audit.json`. These actions are engineering tests, not expert-certified building labels. The complete Next.js HTTP export path also passed the isolated maintenance and P8 regressions.

| Post-change verification | Result |
|---|---|
| Backend unit tests | PASS — 85 tests |
| Frontend tests | PASS — 3 tests |
| Typecheck / lint | PASS |
| Production Docker Next.js build | PASS; final image deployed locally |
| P8 full regression | PASS |
| P9 native tile / synthetic HTTP / PostGIS / review / export / fencing | PASS |
| P9 HTTP deterministic and cancellation regression | PASS |
| Spatial maintenance API / SQL RLS / historical-job regression | PASS |
| Real GPU post-maintenance smoke | PASS — identical A probabilities, approximately 247 ms |
| Local Docker services | Healthy |

Commands: `pnpm typecheck`, `pnpm lint`, `pnpm test`, `.venv/bin/python -m pytest services/api/tests -q`, `sh scripts/compose.sh build web`, `scripts/acceptance_p8.py`, `scripts/acceptance_p9_tile.py`, `scripts/acceptance_p9_http.py`, `scripts/acceptance_spatial_snapshots.py`, and `scripts/acceptance_spatial_maintenance.py` (Python scripts run with the local `.venv/bin/python`).

The maintenance acceptance creates isolated ordinary users and a synthetic raster. It verifies owner/editor changes, viewer API and direct SQL rejection, geometry validation, stale-revision conflicts, versioned support regeneration, edits/deletion after a job is claimed, unchanged frozen inputs, successful execution from the frozen inputs, and subsequent review/export of historical results. Failure-injection unit tests verify failed mask publication and compare-and-swap conflict cleanup. An uncertain database commit retains candidate artifacts rather than risking removal of a committed version.

Actual browser checks at 1440×900 and 1920×1080 used a separate temporary project:

- AOI list menu → rename/description → edit → drag vertex → cancel restores original 269.75 ha; a subsequent saved edit changes area to 254.15 ha.
- Leaving while editing opens the dirty-state guard; “继续工作” retains the draft.
- Prompt list menu → class/description edit → vertex reshape → saved revision 3; stored mask SHA256 differs from the original. Preview shows the current geometry.
- Prompt and AOI delete dialogs require confirmation; deletion removes the items and disables extraction for missing prerequisites.
- The temporary account, project and storage were cleaned. The approved 建筑-基准01 prompt remains unchanged.

Local screenshot evidence: `artifacts/spatial-maintenance-before.png`, `spatial-aoi-edit-1440.png`, `spatial-navigation-guard.png`, `spatial-prompt-edit-1440.png`, `spatial-prompt-reshape-1920.png`, `spatial-delete-confirm-1920.png`, `spatial-maintenance-after-1920.png`. Persistence evidence is in `artifacts/spatial-browser-evidence.json`.

## Persistence and operational limits

- AOI/Prompt deletion is soft deletion. Historical foreign keys and old immutable support objects remain available; no destructive storage garbage collection was added.
- New jobs freeze input snapshots at submission. Existing jobs are explicitly labeled `legacy_current_state_at_migration`; original names changed before migration cannot be reconstructed and are not represented as historically exact.
- Geometry edits remain drafts until Save. Polygon outer vertices support dragging/removal, and rectangle or polygon redraw is available. Existing interior rings are preserved during outer-boundary editing; dedicated hole-editing tools are not included.
- Prompt publication uses unique versioned files and one revision-checked database update. Failed publication never replaces the active geometry/mask pair. An uncertain commit can leave retained orphan files for later reconciliation.
- Actual Worker stop/restart was tested while real jobs were idle; existing completed jobs survived. In-flight cancellation/late-write behavior is covered by synthetic regression, not falsely reported as a separate real-GPU kill-during-inference test.
- The previously implemented official-path/SDPA correction is the frozen tested baseline. This task did not alter preprocessing, slot semantics, query-half extraction or tune thresholds to improve the capability verdict.

**Current task complete. Engineering Integration PASS; building extraction capability NOT PASSED. No P11, multi-shot, language-conditioned segmentation, time-series monitoring or additional adapter work started.**

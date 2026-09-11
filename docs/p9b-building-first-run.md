> Historical first-run record. Final engineering and capability conclusions: [P9B final validation](p9b-real-skysensepp-validation.md). Earlier pending integration notes below describe the state at that run.

# P9B building benchmark: semantic acceptance NOT PASSED

2026-09-11. Real checkpoint and GPU; native-resolution 512 x 512 inputs. Worker HTTP benchmark only, not a persisted platform Job. No registered endpoint/release identity or PostGIS/MapLibre E2E evidence yet.

User approved the fixed roof and outline. Seed 42, slot 24, threshold 0.5. B is same-scene non-overlapping spatial transfer, NOT cross-image generalization.

| Fixture | Mean | Std | Foreground | Area m2 | Runtime ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| A-same-image | 0.073446 | 0.099235 | 1.0513% | 2756 | 248.22 |
| B-same-scene-different-tile | 0.081030 | 0.080341 | 0.0820% | 215 | 243.54 |
| C-unrelated-query | 0.140362 | 0.161446 | 6.0612% | 15889 | 243.63 |
| D-wrong-prompt | 0.353604 | 0.192020 | 31.8127% | 83395 | 246.58 |

Peak allocated GPU memory: 12,059,968,000 bytes (11.23 GiB) each. nvidia-smi includes cache/context (~15.7 GiB). First inference: 1,344 ms; table shows warm requests, excluding startup/network/GIS processing.

A visually identifies some roofs. B has only 215 m2 response; unrelated farmland C has 15,889 m2 false foreground. These do not satisfy positive-transfer/negative-query gates. D changes substantially with vegetation support; this establishes sensitivity, not correct semantic interpretation. Keep the failed results and fixed fixtures. Do not tune thresholds to claim acceptance.

Identity: SkySense++ research-v1, research_only; Torch 2.1.1+cu121, CUDA 12.1, RTX 4090.
Checkpoint SHA256: `32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c`.
Upstream commit: `cb0c6b774471ad3314354041c8fa6aae7d49a9bb`.

Memory fix: the audited MMCV wrapper discards attention weights, yet default MHA materialized a 128 GiB matrix. Set need_weights=False only for these wrappers. Masked CPU numerical equivalence, unchanged state_dict, idempotence and unaffected ordinary MHA tests pass. Strict deterministic mode remains enabled. Repeated A has identical reported probability metrics. Full old/new model numerical comparison is not yet established.

Private inputs, probability .npy/.tif, masks, overlays, requests/responses and metrics remain in ignored artifacts/p9b-building/. Do not upload raster data to GitHub.

GPU 0 cleanup explicitly authorized by user: original process absent; orphan child PPID=1 retained old CUDA context. SIGTERM exited cleanly; GPU memory fell from 15,194 to 608 MiB. Desktop services and current GPU 1 Worker retained.

Next: audit upstream preprocessing/output semantics and model applicability. P9B remains incomplete; do not advance real-model P9C or P11.

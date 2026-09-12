# P10 — SkySense++ Model Capability Validation

**Status: IN PROGRESS / official-GT datasets prepared; formal GT inference/scoring pending.**

This is an interim report, not a P10 PASS or a final model recommendation. No P11, new adapter, product UI or production threshold changes were made for P10. The preceding uncommitted P9C fixes remain separate work.

## Frozen engineering baseline

Checkpoint `32a08982baea125f60feb95fe0a04dfe450ec9c12ee846384cbadd8ff6c5661c`; official source `cb0c6b774471ad3314354041c8fa6aae7d49a9bb`; seed 42; foreground slot 24; existing research-only RTX 4090 Worker. Original A/B/C/D files are SHA256-frozen in `artifacts/p10/baseline-manifest.json`.

New A/B/C 1 m runs are pixel-exact against the frozen P9B arrays (maximum difference 0). No adapter/input wiring rework was performed.

## Current dataset split (2026-09-12)

The user selected separate datasets rather than forcing one collection to answer all questions. WHU aerial continuous fields now support 1/1.5/2/3/4 m input grids with official vector GT. Four WHU Satellite II pairs plus the existing eight SpaceNet2 pairs support satellite-domain comparisons. See `docs/p10/whu-subset.md` and `docs/p10/whu-input-validation.json`. Satellite II webpage GSD conflicts with verified file geometry and must not be taken as 2.7 m without qualification.

WHU data preparation is complete. This does not complete GT model validation. The sections below describe the earlier SPOT6 **no-GT preliminary** screen; its missing-label/coverage statements are specific to those original SPOT6 sources. No new GT F1/IoU or final recommendation is claimed yet.

## Original SPOT6 data and GT audit

Three currently uploaded SPOT6 sources are 1280×1280, 1 m, RGB, EPSG:32630. The supplied external `PASTIS_RECOVERED` directory contains 2432 readable GeoTIFF headers, all 1280×1280, and one empty file. It contains no JSON/GeoJSON/Shapefile/GeoPackage building labels. Header availability does not guarantee every image pixel has been validated. The two nested directories are empty.

The approved building-01 support footprint is NOT complete building GT for any query. An accepted P9 result is also not ground truth. No IoU/Precision/Recall/F1 is reported from unapproved labels.

Sixteen image-only query candidates have been prepared (4 provisional positive, 6 provisional negative, 6 provisional mixed). They include three source scenes; several overlap and are not independent samples. They are a review packet, not a formally frozen complete benchmark. Negative subtypes, including open water and bare ground, still need stratified selection/verification. Some bright objects may be caravans rather than permanent buildings; annotation policy must distinguish these explicitly.

`artifacts/p10/annotation-tool.html` is an offline annotation artifact, not a product UI change. It contains no predictions. A human can outline buildings/ignore regions, record reviewer/completeness and export JSON. No query has yet been marked complete. Building-02/03 and farmland control masks are still pending selection/approval. Vegetation control is the frozen P9B D support.

## Scale validity

A 512×512 output at 3 m requires 1536×1536 native 1 m coverage; 4 m requires 2048×2048. Baseline scene 10014 has no adjacent source patches in the supplied catalog. Therefore 3/4 m runs on the fixed baseline remain unavailable; no padding or PNG enlargement was used.

48 valid georeferenced query grids at 1/1.5/2 m were written with actual updated affine transforms. The 32 attempted 3/4 m grids are explicitly unavailable. RGB uses bilinear geospatial resampling; support mask uses nearest-neighbor reprojection. Edge shifts are recorded. Larger GSD also changes physical scene extent, so raw full-tile statistics alone cannot isolate scale from scene composition.

## Preliminary real GPU runs (no GT scores)

32 fixed-prompt runs: 16 identical queries × frozen building-01 / frozen vegetation control. Plus 12 scale runs: A/B/C × (1→2, 2→2, 2→1, 1.5→1.5). All raw probabilities, georeferenced probability rasters, three threshold masks, overlays and worker metadata are stored. GT images are deliberately absent until actual labels exist.

The 32-run median Worker time is 246.00 ms (range 242.00–249.79 ms), excluding HTTP and GIS. Median correct/wrong absolute probability difference is 0.15977. This proves output sensitivity to support choice, not correct semantic segmentation. No formal IoU/F1 difference can be calculated yet.

| Query | Support→query m | Mean probability | Std | Foreground ≥0.5 |
|---|---|---:|---:|---:|
| Q07 | 1.0→1.0 | 0.14036 | 0.16145 | 6.061% |
| Q14 | 1.0→1.0 | 0.07345 | 0.09924 | 1.051% |
| Q15 | 1.0→1.0 | 0.08103 | 0.08034 | 0.082% |
| Q14 | 1→2 | 0.05337 | 0.13272 | 3.373% |
| Q14 | 2→2 | 0.04167 | 0.09461 | 0.634% |
| Q14 | 2→1 | 0.04727 | 0.08622 | 0.938% |
| Q14 | 1.5→1.5 | 0.04730 | 0.06488 | 0.000% |
| Q15 | 1→2 | 0.04677 | 0.10244 | 1.307% |
| Q15 | 2→2 | 0.03998 | 0.08423 | 0.296% |
| Q15 | 2→1 | 0.04651 | 0.06013 | 0.000% |
| Q15 | 1.5→1.5 | 0.03365 | 0.07041 | 0.023% |
| Q07 | 1→2 | 0.03751 | 0.09392 | 1.606% |
| Q07 | 2→2 | 0.03290 | 0.07820 | 0.301% |
| Q07 | 2→1 | 0.09211 | 0.13105 | 3.736% |
| Q07 | 1.5→1.5 | 0.03139 | 0.06756 | 0.777% |

Q14=A same-image; Q15=B same-scene different tile; Q07=C agricultural query. These preliminary response statistics must not be relabeled as accuracy or proof that scale fixes agricultural false positives. Threshold 0.5 remains primary; 0.3/0.7 remain descriptive only.

## Eight requested final questions — unresolved gates

1. True building F1/IoU: pending formal inference/scoring on the now-prepared official GT; preliminary SPOT6 queries still lack complete GT.
2. Is 1 m suitable: not established; response changes across tested scales are insufficient to determine accuracy.
3. Best GSD: undetermined; original SPOT6 lacks 3/4 m coverage, but separate WHU aerial 1–4 m official-GT inputs are now ready for experiments.
4. Stability across three building prompts: pending building-02/03 approval and experiment.
5. Wrong Prompt effect: existing vegetation control changes probabilities substantially; semantic correctness and farmland control remain unverified.
6. Cross-tile versus same-region performance drop: cannot calculate F1 drop without GT. Cross-image raw responses are retained separately.
7. Why farmland false positives: causal explanation not established. Lower response at a different scale is not proof of improved rejection.
8. Dominant cause: **NOT YET CLASSIFIED**. Do not prematurely choose SCALE_DOMINANT / DOMAIN_DOMINANT / PROMPT_GENERALIZATION_WEAK / FOREGROUND_BIAS / MIXED.

Final model recommendation is deferred. The existing research-only usage policy remains unchanged; that is not a new P10 verdict.

## Remaining work

Freeze three building/two wrong prompts and the revised official-GT benchmark with ignore masks; retain SPOT6 A/B/C/D unchanged; run the aerial scale matrix and separate satellite-domain paired matrix; compute GT metrics and common-area scale comparisons; complete the eight answers and final model decision. Stop after P10. No experiment completion or final results commit is claimed here.

## Reproducibility and evidence

- Plan: `docs/p10/experiment-plan.md`.
- Preliminary numeric table: `docs/p10/preliminary-metrics.csv` (empty GT metrics mean unavailable, never zero).
- Local manifests: `artifacts/p10/{baseline-manifest,source-inventory,external-catalog,candidate-manifest,preliminary-integrity}.json`.
- Local raw runs: `artifacts/p10/fixed-prompt-screen/`, `artifacts/p10/scale-screen/`, `artifacts/p10/scale-grids/`.
- Offline modules/tests: `scripts/p10/`; Worker URL/release are injected from local registered configuration, not hardcoded in runner scripts.
- Original P9B artifacts remain intact; raw private imagery stays outside Git. Tracked summaries reference immutable evidence hashes.

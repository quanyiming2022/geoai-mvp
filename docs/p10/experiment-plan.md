# P10 SkySense++ capability validation plan

Scope: diagnostics only. No UI, production inference pipeline, adapter or P11 changes.

1. Freeze checkpoint, official source, local bridge/adapter/contract hashes, seed 42, foreground slot 24, baseline prompt and original A/B/C/D artifact hashes. Record existing uncommitted P9C changes separately; do not mix their commit with P10.
2. Inventory source rasters and physical footprint. Select 12–20 queries with positive/negative/mixed scene strata; label same/near region, distant same-scene, and independent-scene separately. Record overlap; never treat overlapping tiles as independent samples.
3. Prepare image-only annotation packets without model output. Digitize complete building footprints and explicit void/uncertain areas; obtain human review before GT scoring. Baseline support mask alone is not complete query GT. Freeze three building supports and two non-building controls before inspecting new predictions.
4. Construct georeferenced grids from original raster using affine transforms and bilinear RGB resampling; nearest-neighbor categorical masks. Require a fully valid 512×512 output footprint. No padding/PNG resize masquerading as a larger physical footprint. Test 1, 1.5, 2, 3, 4 m where actual source coverage permits.
5. Use fixed queries for every prompt comparison within a scale. Matched-scale pairs and 1→2/2→1 comparisons; retain physical-footprint differences as a confound and report paired common-area metrics if comparing scales. No threshold tuning. Primary threshold 0.5; descriptive 0.3/0.7.
6. Run existing HTTP Worker contract, verify model/checkpoint identity every run, save raw probabilities/georeferencing, all masks and metrics. Do not claim causal attribution from a single scene or prompt.
7. Aggregate per-image and micro metrics with denominators, separate negative-tile FP area, stratify region/scale/prompt. Empty GT: precision undefined if no positive predictions; recall/IoU/F1 undefined if both truth and prediction empty. No fabricated perfect scores.
8. Report eight requested answers and evidence classification; stop after P10. Mark unavailable data, GT or scale combinations explicitly instead of inventing results.

Artifacts: private source imagery, annotation packets and probability arrays stay in ignored `artifacts/p10/`; tracked scripts, experiment config, aggregate tables and report reference SHA256 manifests. Original P9B artifacts are read-only inputs.

# WHU P10: separate scale and satellite-domain datasets

Official source: https://gpcv.whu.edu.cn/data/building_dataset.html
Local data root: `/Volumes/Extreme SSD/数据集/WHU_P10_subset`.

## Experimental roles

- **Christchurch aerial:** two continuous 2,304 × 2,304 m regions, derived at 0.3 m from the official 0.075 m georeferenced whole-image TIFF (explicit official 4× internal overview). Original whole-area manually annotated building shapefile retained. These are geospatial crops, not resized PNGs. Target 512² grids at 1 / 1.5 / 2 / 3 / 4 m are generated from the same continuous source with updated affine transforms; original vector GT is rasterized independently on each target grid.
- **WHU Satellite II:** four official test image/label pairs (`42`, `43`, `1551`, `3725`), official whole-image vectors and small whole-label files. Crops 42 and 43 are adjacent; others sample more distant positions. No full satellite-image archive is downloaded.
- **SpaceNet2:** existing eight-pair Shanghai/Las Vegas pilot stays unchanged for cross-city, sensor/domain, and prompt comparisons. It cannot supply 1–4 m 512² inputs from its small physical chips.

No model capability verdict follows from preparing any of these inputs.

## Satellite georeferencing verification

Original 512² satellite TIFFs have no CRS or affine transform. Every selected binary label was matched to exactly one 512² window in official `whole-labels/test.tif`, with **262,144 / 262,144 identical pixels**. That file's world transform and `EA.prj` (EPSG:3395) locate the crop. Re-rasterizing the corresponding official vectors matches each supplied chip label at **IoU 1.0**. Derived georeferenced TIFFs are separate from original bytes.

The website says Satellite II is 2.7 m. Its downloaded whole-label world file instead has 0.33956958 m projected grid spacing; verified geometry implies approximately **0.262 m ground spacing** in this subset. Both facts are recorded. Do not label these four downloaded inputs as 2.7 m or silently override this conflict in scale conclusions.

## Limits

- Fixed 512² input with varying GSD changes physical field of view. A later scale comparison must report full-window metrics and a common geographic evaluation core; otherwise content/FOV changes confound scale effects.
- Ground truth is an official building footprint annotation, not automatically a visible roof mask; visual alignment still needs inspection.
- Aerial and satellite metrics must be reported separately. An aerial scale optimum does not demonstrate the same optimum for SPOT6.
- Dataset licensing is recorded from the official source; no commercial license is inferred from public download availability. Do not commit raw data to Git.

## Reproduction

Offline/download scripts: `scripts/p10/whu/` (requires the project's rasterio/numpy/httpx and `pyshp`; the latter was installed into an isolated temporary directory, not the application).

1. `download_subset.py`: complete small 34 MB aerial vector archive and selected ZIP members only.
2. `download_regions.py`: two georeferenced aerial crops through an HTTP range proxy with a 384 MiB transfer budget; small full-area satellite labels only.
3. `match_satellite.py`: exact chip-label placement.
4. `validate_satellite.py`: vector/label agreement before attaching derived georeferencing.
5. `validate_scales.py`: grid/coverage checks, five GSD inputs per aerial region, SHA256 inventory.

Local validation completed: two aerial crops, four satellite pairs, ten legal target grids. Every target grid is spatially inside its source; seven grids contain 2–35 source NoData pixels, retained in valid masks and excluded from future scores. Three grids have all 262,144 pixels valid. `docs/p10/whu-input-validation.json` records the actual checks. Dataset preparation is complete; model capability experiments are not.

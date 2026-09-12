# SpaceNet 2 small supplementary subset

Downloaded from official public S3, matched original RGB/GeoJSON pairs. Local destination: `/Volumes/Extreme SSD/数据集/SpaceNet2_P10_subset`.

Shanghai 4 + Las Vegas 4 active chips, 650×650 uint16 RGB. Includes one empty-label control per city and six building-containing samples. 149 official building polygons total. All active images have a complete native 512×512 nonzero/valid window; all source geometries validated with existing read-only PostGIS. No repairs or model inference performed.

Downloaded 22,964,156 bytes (21.90 MiB), including one Vegas black-border rejection retained with an exclusion flag. 8 active + 1 excluded pair. No archive tarballs/MS/PAN. Original bytes and SHA256 retained; binary GT, valid masks, label overlays and overview generated locally. Display stretch is explicitly not a model input recipe.

Official source/license: https://spacenet.ai/spacenet-buildings-dataset-v2/ — CC BY-SA 4.0. Building labels provide supplementary GT, not labels for frozen SPOT6 imagery. Chips are too small in physical footprint for the SPOT6 1–4m/512 protocol; report native-resolution cross-dataset results separately. This small convenience pilot is not a representative city benchmark.

Reproducers: `scripts/p10/download_spacenet2_subset.py`, `scripts/p10/validate_spacenet2_subset.py`. Download script refuses overwriting an existing frozen manifest. URLs, object sizes and hashes are in the external subset manifest; validation and source attribution in its README.

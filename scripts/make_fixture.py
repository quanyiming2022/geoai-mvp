"""Generate a deterministic local QA GeoTIFF, no external data download."""

from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin


def make_fixture(path, dimension=256, compress="deflate"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[:dimension, :dimension]
    bands = np.stack(
        [((x // 32 + y // 32) % 2) * 100 + 40, 100 + x // 3, 60 + y // 4]
    ).astype("uint8")
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=dimension,
        height=dimension,
        count=3,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(116.3, 40.0, 0.0001, 0.0001),
        compress=compress,
    ) as dataset:
        dataset.write(bands)
    return path


if __name__ == "__main__":
    print(
        make_fixture(Path(__file__).resolve().parents[1] / "artifacts/demo-geotiff.tif")
    )

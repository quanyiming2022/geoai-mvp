import numpy as np
import pytest
from geoai.raster_processing import tile_bounds, rgba_png


def test_web_mercator_xyz_bounds():
    b = tile_bounds(0, 0, 0)
    assert b[0] == pytest.approx(-20037508.342789244)
    assert b[2] == pytest.approx(20037508.342789244)
    assert tile_bounds(1, 0, 0)[2:] == pytest.approx((0, 20037508.342789244))
    with pytest.raises(ValueError):
        tile_bounds(1, 2, 0)


def test_png_contains_rgba_pixels():
    data = np.ones((3, 16, 16), dtype="uint8") * 100
    png = rgba_png(data, np.ones((16, 16), dtype="uint8") * 255)
    assert png.startswith(b"\x89PNG")


@pytest.mark.parametrize("count", [2, 4])
def test_existing_alpha_tiles(count, tmp_path):
    import rasterio
    from rasterio.enums import ColorInterp
    from rasterio.transform import from_bounds
    from rasterio.io import MemoryFile
    from geoai.raster_processing import render_tile

    path = tmp_path / "alpha.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=16,
        height=16,
        count=count,
        dtype="uint8",
        crs="EPSG:3857",
        transform=from_bounds(*tile_bounds(0, 0, 0), 16, 16),
    ) as ds:
        ds.write(np.full((count, 16, 16), 150, dtype="uint8"))
        ds.colorinterp = (
            (ColorInterp.gray, ColorInterp.alpha)
            if count == 2
            else (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
        )
    with MemoryFile(render_tile(path, 0, 0, 0)) as memory, memory.open() as ds:
        assert ds.count == 4 and ds.read(4).max() > 0


def test_global_stretch_same_value_same_color():
    from rasterio.io import MemoryFile

    ranges = [[0, 1000]] * 3
    one = np.full((3, 2, 2), 500, dtype="uint16")
    two = one.copy()
    two[:, 0, 0] = 1000
    with MemoryFile(rgba_png(one, np.full((2, 2), 255), ranges)) as m, m.open() as d:
        a = d.read()[:, 1, 1]
    with MemoryFile(rgba_png(two, np.full((2, 2), 255), ranges)) as m, m.open() as d:
        b = d.read()[:, 1, 1]
    assert np.array_equal(a, b)


def test_timeout_cleanup_and_redis_failure_independent(monkeypatch):
    import tempfile
    from pathlib import Path
    from geoai import worker

    import multiprocessing
    import time

    active = multiprocessing.get_context("spawn").Process(target=time.sleep, args=(60,))
    active.start()

    class Config:
        raster_timeout_seconds = 10

    class BrokenRedis:
        def set(self, *a, **k):
            raise ConnectionError()

    calls = []
    monkeypatch.setattr(worker, "fail", lambda cfg, row, code: calls.append(code))
    scratch = tempfile.TemporaryDirectory()
    path = Path(scratch.name)
    (path / "partial.tif").write_bytes(b"partial")
    worker.heartbeat(BrokenRedis())
    assert worker.supervise(active, {}, scratch, 0, Config()) is False
    assert not path.exists() and calls == ["processing_timeout"]

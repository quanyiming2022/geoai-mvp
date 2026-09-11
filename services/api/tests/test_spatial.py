import pytest
from pydantic import ValidationError
from geoai.spatial import PolygonInput


def test_polygon_rejects_unclosed_nonfinite_and_out_of_range():
    for ring in (
        [[0, 0], [1, 0], [0, 1]],
        [[0, 0], [200, 0], [0, 1], [0, 0]],
        [[179, 0], [-179, 0], [179, 1], [179, 0]],
        [[0, 0], [1, float("nan")], [0, 1], [0, 0]],
    ):
        with pytest.raises(ValidationError):
            PolygonInput(type="Polygon", coordinates=[ring])
    assert PolygonInput(type="Polygon", coordinates=[[[0, 0], [1, 0], [0, 1], [0, 0]]])

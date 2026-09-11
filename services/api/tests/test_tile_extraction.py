from uuid import uuid4
import numpy as np
import pytest
from pydantic import ValidationError
from rasterio.transform import from_origin
from geoai.jobs import JobInput
from geoai.tile_extraction import tile_polygons


def test_tile_job_is_opt_in_and_url_free():
    values=dict(kind='geoextract_tile',idempotency_key=uuid4(),prompt_id=uuid4(),raster_asset_id=uuid4(),model_endpoint_id=uuid4(),model_release_id=uuid4(),endpoint_revision=1,query_col=0,query_row=0,seed=57)
    assert JobInput(**values).query_col==0
    for override in ({'query_row':True},{'aoi_id':uuid4()},{'model_url':'http://localhost'},{'kind':'geoextract'},{'seed':None}):
        with pytest.raises(ValidationError):
            JobInput(**{**values,**override})


def test_tile_polygons_have_real_probability_confidence_and_valid_pixel_mask():
    values=np.zeros((512,512),dtype='float32')
    values[20:30,40:50]=.8
    values[20:25,40:50]=.6
    valid=np.ones((512,512),dtype=bool)
    valid[20,:]=False
    binary,polygons=tile_polygons(values,valid,from_origin(0,1,.001,.001),'EPSG:4326')
    assert binary.sum()==90 and len(polygons)==1
    geometry,mean,maximum=polygons[0]
    assert geometry['type']=='Polygon'
    assert mean==pytest.approx((40*.6+50*.8)/90) and maximum==pytest.approx(.8)

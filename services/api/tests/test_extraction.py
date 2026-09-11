import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from geoai.extraction import mock_polygons,persist_results


def blob(data,transform):
    with MemoryFile() as memory:
        with memory.open(driver='GTiff',width=data.shape[2],height=data.shape[1],count=data.shape[0],dtype=data.dtype,crs='EPSG:4326',transform=transform) as ds:
            ds.write(data)
        return memory.read()


def test_mock_polygons_use_actual_aoi_pixel_grid():
    transform=from_origin(116,40,.001,.001)
    image=blob(np.full((3,8,8),100,dtype='uint8'),transform)
    mask=np.zeros((1,8,8),dtype='uint8')
    mask[:,2:6,2:6]=1
    binary=blob(mask,transform)
    result=mock_polygons(image,binary,image,binary)
    assert len(result)==1
    points=result[0]['coordinates'][0]
    assert min(p[0] for p in points)==pytest.approx(116.002)
    assert max(p[1] for p in points)==pytest.approx(39.998)
    assert min(p[1] for p in points)==pytest.approx(39.994)


def test_cancelled_job_cannot_persist_any_predictions(monkeypatch):
    queries=[]
    class Conn:
        def __enter__(self):
            return self
        def __exit__(self,*args):
            pass
        def execute(self,query,params):
            queries.append(query)
            return self
        def fetchone(self):
            return None
    monkeypatch.setattr('geoai.extraction.database',lambda cfg:Conn())
    persist_results(None,{'id':'cancelled','claim_token':'old'},[{}],{})
    assert len(queries)==1 and queries[0].startswith('SELECT')

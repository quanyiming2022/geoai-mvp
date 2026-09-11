import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from geoai.native_tile import read_native_tile


def test_query_is_source_resolution_window_not_overview_resize(tmp_path):
    path=tmp_path/'large.tif'
    yy,xx=np.indices((1024,1024))
    data=np.stack([xx%256,yy%256,(xx+yy)%256]).astype('uint8')
    transform=from_origin(116,40,.0001,.0001)
    with rasterio.open(path,'w',driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=transform) as ds:
        ds.write(data)
    rgb,valid,actual,crs=read_native_tile(str(path),201,307)
    assert np.array_equal(rgb,data[:,307:819,201:713])
    assert actual.a==transform.a and actual.e==transform.e and crs=='EPSG:4326'
    assert valid.shape==(512,512) and valid.all()
    with pytest.raises(ValueError):
        read_native_tile(str(path),800,800)

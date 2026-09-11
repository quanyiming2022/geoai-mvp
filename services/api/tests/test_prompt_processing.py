import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from rasterio.warp import transform_geom
from geoai.prompt_processing import support_crop


@pytest.mark.parametrize('crs,transform', [('EPSG:4326',from_origin(116,40,.001,.001)),('EPSG:3857',from_origin(0,1000,10,10))])
def test_support_image_and_binary_mask_share_grid(tmp_path,crs,transform):
    source=tmp_path/'source.tif'
    with rasterio.open(source,'w',driver='GTiff',width=100,height=100,count=3,dtype='uint8',crs=crs,transform=transform) as ds:
        ds.write(np.full((3,100,100),100,dtype='uint8'))
    points=[transform*p for p in [(20,20),(70,20),(20,70),(20,20)]]
    geometry=transform_geom(crs,'EPSG:4326',{'type':'Polygon','coordinates':[points]})
    image,mask,result_crs=support_crop(str(source),geometry)
    with MemoryFile(image) as im,MemoryFile(mask) as mm, im.open() as a,mm.open() as b:
        assert result_crs==crs and a.crs==b.crs and a.transform==b.transform and a.shape==b.shape
        assert set(np.unique(b.read(1)))=={0,1} and a.read().min()==100
        assert max(a.shape)<=512


def test_no_valid_pixels_rejected(tmp_path):
    path=tmp_path/'nodata.tif'
    with rasterio.open(path,'w',driver='GTiff',width=10,height=10,count=1,dtype='uint8',nodata=0,crs='EPSG:4326',transform=from_origin(0,1,.1,.1)) as ds:
        ds.write(np.zeros((1,10,10),dtype='uint8'))
    with pytest.raises(ValueError,match='no valid target'):
        support_crop(str(path),{'type':'Polygon','coordinates':[[[.2,.2],[.4,.2],[.4,.4],[.2,.2]]]})


def test_rotated_raster_rejects_partial_outside_sample(tmp_path):
    path=tmp_path/'rotated.tif'
    transform=from_origin(0,1,.01,.01)*rasterio.Affine.rotation(45)
    with rasterio.open(path,'w',driver='GTiff',width=64,height=64,count=1,dtype='uint8',crs='EPSG:4326',transform=transform) as ds:
        ds.write(np.ones((1,64,64),dtype='uint8'))
    points=[transform*p for p in [(-2,10),(20,10),(20,30),(-2,10)]]
    with pytest.raises(ValueError,match='outside the raster pixel footprint'):
        support_crop(str(path),{'type':'Polygon','coordinates':[points]})

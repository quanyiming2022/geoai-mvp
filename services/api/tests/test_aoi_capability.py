import pytest
from affine import Affine
from rasterio.io import MemoryFile
from geoai.map_window import plan_full_aoi

@pytest.mark.parametrize('width,height,mode',[(100,80,'single_tile_full_aoi'),(512,512,'single_tile_full_aoi'),(513,100,'multi_tile_full_aoi'),(100,513,'multi_tile_full_aoi')])
def test_source_pixel_capacity(width,height,mode):
    t=Affine.translation(116,40)*Affine.rotation(13)*Affine.scale(.0001,-.0001)
    ring=[list(t*p) for p in [(100,120),(100+width,120),(100+width,120+height),(100,120+height),(100,120)]]
    with MemoryFile() as mem,mem.open(driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=t) as ds:
        plan=plan_full_aoi(ds,{'type':'Polygon','coordinates':[ring]})
    assert plan['execution_mode']==mode
    assert plan['aoi_bbox_width_px']==pytest.approx(width)
    assert plan['aoi_bbox_height_px']==pytest.approx(height)
    assert plan['available']==(mode=='single_tile_full_aoi')
    if plan['available']:
        assert plan['query_col']<=100+1e-7 and plan['query_col']+512>=100+width-1e-7
        assert plan['query_row']<=120+1e-7 and plan['query_row']+512>=120+height-1e-7

@pytest.mark.parametrize('left,top',[(0,0),(950,950)])
def test_small_edge_aoi_is_shifted_inside_raster(left,top):
    t=Affine(1,0,0,0,-1,1024);ring=[list(t*p) for p in [(left,top),(left+50,top),(left+50,top+50),(left,top+50),(left,top)]]
    with MemoryFile() as mem,mem.open(driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:3857',transform=t) as ds:
        from rasterio.warp import transform_geom
        plan=plan_full_aoi(ds,transform_geom(ds.crs,'EPSG:4326',{'type':'Polygon','coordinates':[ring]}))
    assert plan['available']
    assert 0<=plan['query_col']<=left and plan['query_col']+512>=left+50
    assert 0<=plan['query_row']<=top and plan['query_row']+512>=top+50


def test_small_aoi_outside_source_cannot_claim_complete_coverage():
    with MemoryFile() as mem,mem.open(driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=Affine(.001,0,0,0,-.001,1)) as ds:
        plan=plan_full_aoi(ds,{'type':'Polygon','coordinates':[[[-.01,.9],[.02,.9],[.02,.8],[-.01,.8],[-.01,.9]]]})
    assert not plan['available'] and plan['reason']=='outside_raster'

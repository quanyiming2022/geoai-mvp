import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from geoai.map_window import select_window
from geoai.tile_extraction import effective_valid_mask,tile_polygons,geotiff


def polygon(left,bottom,right,top):return {'type':'Polygon','coordinates':[[[left,bottom],[right,bottom],[right,top],[left,top],[left,bottom]]]}

def test_small_aoi_window_keeps_complete_native_context():
    with MemoryFile() as mem:
        with mem.open(driver='GTiff',width=1024,height=1024,count=3,dtype='uint8',crs='EPSG:4326',transform=from_origin(0,1,.001,.001)) as ds:
            aoi=polygon(.3,.3,.7,.7)
            selected=select_window(ds,.301,.699,aoi)
            assert selected['width']==selected['height']==512
            assert selected['query_col']<=300 and selected['query_col']+512>=700
            assert selected['query_row']<=300 and selected['query_row']+512>=700

def test_effective_pixels_exclude_outside_aoi_without_changing_model_input():
    t=from_origin(0,1,.001,.001);valid=np.ones((512,512),dtype=bool)
    aoi=polygon(.1,.66,.14,.70)
    effective=effective_valid_mask(valid,t,'EPSG:4326',aoi)
    assert effective.sum()==1600 and valid.all()
    probability=np.full((512,512),.9,dtype='float32')
    binary,polygons=tile_polygons(probability,effective,t,'EPSG:4326')
    assert binary.sum()==1600 and len(polygons)==1
    assert not binary[~effective].any()
    data=np.where(effective,probability,np.nan).astype('float32')
    with MemoryFile(geotiff(data,t,'EPSG:4326')) as mem,mem.open() as ds:
        assert ds.read(1,masked=True).mask.sum()==512*512-1600
    assert np.all(probability==.9)

def test_no_aoi_preserves_legacy_valid_pixels_and_tiny_aoi_is_not_error():
    t=from_origin(0,1,.001,.001);valid=np.ones((512,512),dtype=bool)
    assert effective_valid_mask(valid,t,'EPSG:4326') is valid
    tiny=effective_valid_mask(valid,t,'EPSG:4326',polygon(.10001,.89991,.10002,.89992))
    binary,polygons=tile_polygons(np.ones((512,512),dtype='float32'),tiny,t,'EPSG:4326')
    assert binary.sum()==0 and polygons==[]

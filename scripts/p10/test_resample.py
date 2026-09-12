import numpy as np,pytest
from rasterio.io import MemoryFile
from affine import Affine
from resample import grid_for,rgb_grid

def test_georeference_and_footprint():
 with MemoryFile() as f:
  with f.open(driver='GTiff',width=1280,height=1280,count=3,dtype='uint8',crs='EPSG:32630',transform=Affine(1,0,600000,0,-1,5400000)) as ds:
   ds.write(np.ones((3,1280,1280),dtype='uint8')*75)
   t=grid_for(ds,1100,1100,2)
   assert t.a==2 and t.e==-2 and t.c==600256 and t.f==5399744
   assert np.all(rgb_grid(ds,t)==75)
   for g in (3,4):
    with pytest.raises(ValueError,match='INSUFFICIENT'):grid_for(ds,640,640,g)

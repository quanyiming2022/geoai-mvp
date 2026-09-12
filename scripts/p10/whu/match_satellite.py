from pathlib import Path
import json,hashlib,sys,os
import numpy as np,rasterio,shapefile
from rasterio.windows import Window
from rasterio.features import rasterize
D=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'))/'satellite-ii'
want={};result=[]
for p in (D/'label').glob('[0-9]*.tif'):
 with rasterio.open(p) as ds:a=(ds.read(1)>0).astype('uint8');want[hashlib.sha256(a.tobytes()).hexdigest()]=(p.name,a)
with rasterio.open(D/'whole-labels/test.tif') as full:
 for row in range(0,full.height-511,512):
  band=(full.read(1,window=Window(0,row,full.width,512))>0).astype('uint8')
  for col in range(0,full.width-511,512):
   mask=band[:,col:col+512];key=hashlib.sha256(mask.tobytes()).hexdigest()
   if key in want:
    name,a=want[key];assert np.array_equal(a,mask);win=Window(col,row,512,512)
    result.append({'image':name,'whole_label':'test.tif','window':[col,row,512,512],'transform':list(full.window_transform(win))[:6],'bounds':list(rasterio.windows.bounds(win,full.transform)),'match':'exact binary GT 262144/262144 pixels'})
 print('matches',json.dumps(result,indent=2),flush=True)
(D/'chip-placement.json').write_text(json.dumps(result,indent=2))

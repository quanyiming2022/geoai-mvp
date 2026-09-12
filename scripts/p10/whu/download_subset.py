import sys,json,zipfile,hashlib,shutil,os
from pathlib import Path
from urllib.parse import quote
import httpx
from whu_range import Remote
DEST=Path(os.environ.get('P10_WHU_DATA_ROOT','/Volumes/Extreme SSD/数据集/WHU_P10_subset'));DEST.mkdir(exist_ok=True)
base='https://gpcv.whu.edu.cn/data/'
rows=[]
# Small complete vector archive only (34 MB); retain official archive and extracted files.
u=base+quote('2. The shape file of the whole area.zip');archive=DEST/'aerial-whole-area-shapefile.zip'
if not archive.exists():
 with httpx.Client(timeout=60) as c,c.stream('GET',u) as r:
  r.raise_for_status();size=0
  with archive.with_suffix('.partial').open('wb') as f:
   for b in r.iter_bytes(1024**2):
    size+=len(b);assert size<=35*1024**2;f.write(b)
  archive.with_suffix('.partial').rename(archive)
assert archive.stat().st_size==34226515
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 folder=DEST/'aerial-vectors';folder.mkdir(exist_ok=True)
 for i in z.infolist():
  if not i.is_dir():
   p=folder/Path(i.filename).name;p.write_bytes(z.read(i));rows.append({'path':str(p.relative_to(DEST)),'source_url':u,'zip_member':i.filename,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
print('Aerial vectors downloaded and CRC checked',flush=True)
u=base+quote('Satellite dataset Ⅱ (East Asia).zip');remote=Remote(u);z=zipfile.ZipFile(remote);names=z.namelist()
images=[n for n in names if '/test/image/' in n and n.endswith('.tif')]
images=sorted(images,key=lambda n:int(Path(n).stem));selected=[images[0],images[1],images[len(images)//2],images[-1]]
for name in selected:
 label=name.replace('/image/','/label/');assert label in names,label
for name in selected+[n.replace('/image/','/label/') for n in selected]+[n for n in names if '/2. The shape file' in n and Path(n).suffix in ['.shp','.shx','.dbf','.prj','.xml']]:
 i=z.getinfo(name);assert i.file_size<20*1024**2
 kind='vectors' if '/2. ' in name else 'image' if '/image/' in name else 'label';p=DEST/'satellite-ii'/kind/Path(name).name;p.parent.mkdir(parents=True,exist_ok=True)
 with z.open(i) as src,p.open('wb') as dst:shutil.copyfileobj(src,dst,1024**2)
 rows.append({'path':str(p.relative_to(DEST)),'source_url':u,'zip_member':name,'zip_crc32':f'{i.CRC:08x}','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size});print('Downloaded',str(p.relative_to(DEST)),p.stat().st_size,flush=True)
(DEST/'download-manifest.json').write_text(json.dumps({'official_page':'https://gpcv.whu.edu.cn/data/building_dataset.html','satellite_archive_range_bytes':remote.total,'files':rows},indent=2,ensure_ascii=False))
print('Satellite selected members range transferred',remote.total,'bytes',flush=True)

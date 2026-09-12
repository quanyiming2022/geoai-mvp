"""Download eight matched official SN2 RGB/label pairs, with a hard 40 MiB transfer cap."""
import hashlib,json,time,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
import httpx
DEST=Path('/Volumes/Extreme SSD/数据集/SpaceNet2_P10_subset')
BASE='https://spacenet-dataset.s3.amazonaws.com/'
NS={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
CAP=40*1024**2

def listing(c,prefix):
 r=c.get(BASE,params={'list-type':'2','prefix':prefix,'max-keys':1000}).raise_for_status()
 root=ET.fromstring(r.content)
 return {n.find('s:Key',NS).text:int(n.find('s:Size',NS).text) for n in root.findall('s:Contents',NS)}

def run():
 DEST.mkdir(exist_ok=True)
 if (DEST/'manifest.json').exists():raise SystemExit('Existing manifest found; refusing to change a frozen subset')
 downloaded=0;records=[]
 with httpx.Client(timeout=60,trust_env=False,follow_redirects=False) as c:
  for city in ['AOI_4_Shanghai','AOI_2_Vegas']:
   prefix=f'spacenet/SN2_buildings/train/{city}/';images=listing(c,prefix+'PS-RGB/');labels=listing(c,prefix+'geojson_buildings/')
   pairs=[]
   for key,size in images.items():
    if not key.endswith('.tif'):continue
    label=key.replace('/PS-RGB/','/geojson_buildings/').replace('_PS-RGB_','_geojson_buildings_').replace('.tif','.geojson')
    if label in labels:pairs.append((key,size,label,labels[label]))
   empty=[p for p in pairs if p[3]<500];positive=[p for p in pairs if 500<=p[3]<=200000]
   assert empty and len(positive)>=3
   selected=[empty[0],positive[0],positive[len(positive)//2],positive[-1]]
   # img1 was inspected and has no complete valid 512 window; use inspected replacement.
   if city=='AOI_2_Vegas':selected[1]=next(p for p in positive if p[0].endswith('_img1003.tif'))
   for image,sz,label,lsz in selected:
    row={'city':city,'selection':'one small/empty label and three nonempty labels, first/middle/last of first 1000 matched listing; no model-output selection','objects':[]}
    assert downloaded+sz+lsz<=CAP
    for key,size in [(image,sz),(label,lsz)]:
     target=DEST/city/Path(key).parent.name/Path(key).name;target.parent.mkdir(parents=True,exist_ok=True)
     if target.exists():raise RuntimeError('Refusing to overwrite '+str(target))
     url=BASE+quote(key,safe='/');part=target.with_suffix(target.suffix+'.part');digest=hashlib.sha256();count=0
     with c.stream('GET',url) as r:
      r.raise_for_status()
      with part.open('wb') as f:
       for chunk in r.iter_bytes(1024*256):
        count+=len(chunk);downloaded+=len(chunk)
        if count>size or downloaded>CAP:raise RuntimeError('Download budget exceeded')
        f.write(chunk);digest.update(chunk)
      if count!=size:raise RuntimeError('Size mismatch')
      part.rename(target)
      row['objects'].append({'file':str(target.relative_to(DEST)),'url':url,'bytes':count,'sha256':digest.hexdigest(),'etag':r.headers.get('etag'),'last_modified':r.headers.get('last-modified')})
     print(target.name,count,flush=True)
    records.append(row)
 manifest={'dataset':'SpaceNet 2 Building Detection v2','official_page':'https://spacenet.ai/spacenet-buildings-dataset-v2/','license':'CC BY-SA 4.0 (per official dataset page)','downloaded_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'total_bytes':downloaded,'pairs':records,'selection_limit':'4 per city; 8 RGB + 8 matched building GeoJSON; no tarballs or extra spectral bands'}
 (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
 print('PASS',len(records),'pairs',downloaded,'bytes',DEST)
if __name__=='__main__':run()

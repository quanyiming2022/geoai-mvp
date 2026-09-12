import io,json,httpx,zipfile
from urllib.parse import quote
class Remote(io.RawIOBase):
 def __init__(self,url):
  self.url=url;self.c=httpx.Client(timeout=40,follow_redirects=True);r=self.c.get(url,headers={'Range':'bytes=0-0'});r.raise_for_status();assert r.status_code==206;self.size=int(r.headers['content-range'].split('/')[-1]);self.p=0;self.total=1
 def seekable(self):return True
 def readable(self):return True
 def tell(self):return self.p
 def seek(self,n,w=0):self.p=n if w==0 else self.p+n if w==1 else self.size+n;return self.p
 def read(self,n=-1):
  if n<0:n=self.size-self.p
  n=min(n,self.size-self.p)
  if not n:return b''
  assert n<20*1024**2,('excessive request',n)
  r=self.c.get(self.url,headers={'Range':f'bytes={self.p}-{self.p+n-1}'});r.raise_for_status();assert r.status_code==206 and len(r.content)==n;self.total+=n;self.p+=n;return r.content
if __name__=='__main__':
 for name,key in [('Satellite dataset Ⅱ (East Asia).zip','satellite'),('2. The shape file of the whole area.zip','shapes')]:
  r=Remote('https://gpcv.whu.edu.cn/data/'+quote(name));z=zipfile.ZipFile(r);items=[{'name':i.filename,'size':i.file_size,'compressed':i.compress_size,'offset':i.header_offset} for i in z.infolist()];json.dump(items,open('/tmp/whu-'+key+'-index.json','w'),ensure_ascii=False,indent=2);print(key,len(items),'index bytes',r.total);print(items[:16]);print(items[-8:])

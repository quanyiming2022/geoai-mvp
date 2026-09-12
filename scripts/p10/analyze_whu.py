"""Recompute GT confusion independently, summarize preregistered P10 comparisons."""
import sys,json,csv,hashlib,itertools
from pathlib import Path
import numpy as np,rasterio
from metrics import difference
ROOT=Path(__file__).resolve().parents[2];O=ROOT/'artifacts/p10/whu-formal-v1';DOC=ROOT/'docs/p10'
def dump(p,a):Path(p).write_text(json.dumps(a,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def aggregate(rows,common=False):
 a=[r['common_core'] if common else r for r in rows];tp=sum(x['TP'] for x in a);fp=sum(x['FP'] for x in a);fn=sum(x['FN'] for x in a);n=sum(x['valid_pixels'] for x in a)
 return {'runs':len(a),'TP':tp,'FP':fp,'FN':fn,'valid_pixels':n,'IoU':tp/(tp+fp+fn) if tp+fp+fn else None,'Precision':tp/(tp+fp) if tp+fp else None,'Recall':tp/(tp+fn) if tp+fn else None,'F1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'foreground_ratio':(tp+fp)/n,'false_positive_rate':fp/(n-tp-fn) if n-tp-fn else None,'mean_prob':float(np.mean([x['prob_mean'] for x in a])),'mean_prob_std':float(np.mean([x['prob_std'] for x in a])),'mean_p95':float(np.mean([x['p95'] for x in a])),'mean_p99':float(np.mean([x['p99'] for x in a])),'false_positive_area_sum':sum(x['false_positive_area'] for x in a) if all(x['false_positive_area'] is not None for x in a) else None,'false_negative_area_sum':sum(x.get('false_negative_area',x['FN']) for x in a) if all(x.get('false_negative_area',x['FN']) is not None for x in a) else None,'area_note':'sum over repeated experiments, NOT unique mapped land area'}
def main():
 rows=json.loads((O/'summary.json').read_text());cfg=json.loads((O/'config.json').read_text());assert len(rows)==len(cfg['runs'])==180
 checks=[]
 for r in rows:
  folder=O/'runs'/r['experiment_id'];p=np.load(folder/'probability.npy')
  with rasterio.open(O/'inputs'/r['query_id']/'gt.tif') as d:gt=d.read(1)>0;aff=d.transform;crs=d.crs
  with rasterio.open(O/'inputs'/r['query_id']/'valid.tif') as d:v=d.read(1)>0
  with rasterio.open(folder/'probability.tif') as d:assert d.transform==aff and d.crs==crs and np.array_equal(d.read(1),p)
  assert p.shape==(512,512) and np.isfinite(p).all() and p.min()>=0 and p.max()<=1
  pred=p>=.5;tp=np.count_nonzero(pred& gt&v);fp=np.count_nonzero(pred&~gt&v);fn=np.count_nonzero(~pred&gt&v)
  assert (tp,fp,fn)==(r['TP'],r['FP'],r['FN'])
  assert abs((2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)-(r['F1'] or 0))<1e-10
  for n in ['support.png','support_mask.png','query.png','gt.png','pred_03.png','pred_05.png','pred_07.png','overlay.png','metadata.json']:assert (folder/n).exists()
  with rasterio.open(folder/'support_mask.png') as d:assert set(np.unique(d.read(1))).issubset({0,1})
 groups={}
 matched=[r for r in rows if r['query_region']!='satellite' and r['prompt_type']=='building' and r['query_gsd']==r['support_gsd']]
 for region in ['urban','outskirts']:
  for g in [1.,1.5,2.,3.,4.]:
   a=[r for r in matched if r['query_region']==region and r['query_gsd']==g]
   groups[f'{region}:{g:g}m']={'full':aggregate(a),'common':aggregate(a,True)}
 prompts={}
 for p in ['P1','P2','P3']:
  for region in ['urban','outskirts']:
   for g in [1.,1.5,2.,3.,4.]:
    a=[r for r in matched if r['prompt']==p and r['query_region']==region and r['query_gsd']==g];prompts[f'{p}:{region}:{g:g}m']=aggregate(a)
 cross={}
 for region in ['urban','outskirts']:
  for sg,qg in [(1.,1.),(1.,1.5),(1.,2.),(1.,3.),(1.,4.),(2.,1.),(2.,2.)]:
   a=[r for r in rows if r['prompt_type']=='building' and r['query_region']==region and r['support_gsd']==sg and r['query_gsd']==qg];cross[f'{region}:{sg:g}>{qg:g}']={'full':aggregate(a),'common':aggregate(a,True)}
 pairs=[]
 for q in cfg['queries']:
  a=[r for r in rows if r['query_id']==q['id'] and r['prompt_type']=='building' and (q['region']=='satellite' and r['support_region']=='satellite' or q['gsd'] and r['support_gsd']==q['gsd'])]
  b=[r for r in rows if r['query_id']==q['id'] and r['prompt_type']=='wrong']
  with rasterio.open(O/'inputs'/q['id']/'valid.tif') as d:v=d.read(1)>0
  with rasterio.open(O/'inputs'/q['id']/'gt.tif') as d:building=(d.read(1)>0)&v
  for correct,wrong in itertools.product(a,b):
   p=np.load(O/'runs'/correct['experiment_id']/'probability.npy');w=np.load(O/'runs'/wrong['experiment_id']/'probability.npy')
   delta=w-p
   out=O/'comparisons'/f'{correct["experiment_id"]}__vs__{wrong["support_id"]}';out.mkdir(parents=True,exist_ok=True);np.save(out/'wrong-minus-correct.npy',delta)
   row={'query':q['id'],'region':q['region'],'correct':correct['support_id'],'wrong':wrong['support_id'],'F1_correct':correct['F1'],'F1_wrong':wrong['F1'],'IoU_correct':correct['IoU'],'IoU_wrong':wrong['IoU'],'building_prob_correct':float(p[building].mean()) if building.any() else None,'building_prob_wrong':float(w[building].mean()) if building.any() else None,'building_recall_correct':correct['Recall'],'building_recall_wrong':wrong['Recall'],'F1_wrong_minus_correct':wrong['F1']-correct['F1'] if wrong['F1'] is not None and correct['F1'] is not None else None,**difference(p,w,v)};pairs.append(row)
 sat={}
 native=[r for r in rows if r['query_region']=='satellite' and r['support_region']=='satellite' and r['prompt_type']=='building']
 for label,a in [('same_image',[r for r in native if r['query_id']==r['support_id']]),('cross_scene',[r for r in native if r['query_id']!=r['support_id']]),('aerial_to_satellite',[r for r in rows if r['query_region']=='satellite' and r['support_region']=='urban'])]:sat[label]=aggregate(a)
 rt=[r['runtime_ms'] for r in rows];mem=[r['peak_gpu_memory_mb'] for r in rows if r['peak_gpu_memory_mb'] is not None]
 result={'matched_scale':groups,'prompt_by_scale':prompts,'cross_scale':cross,'satellite':sat,'runtime_ms':{'min':min(rt),'median':float(np.median(rt)),'p95':float(np.percentile(rt,95)),'max':max(rt)},'peak_gpu_memory_mb':{'min':min(mem),'max':max(mem)} if mem else None,'verified_runs':len(rows),'paired_prompt_comparisons':len(pairs)}
 dump(O/'analysis.json',result);dump(O/'prompt-comparisons.json',pairs);dump(DOC/'whu-formal-analysis.json',result)
 flat=[]
 for r in rows:
  a={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
  if r['common_core']:a.update({'core_'+k:v for k,v in r['common_core'].items() if not isinstance(v,(dict,list))})
  flat.append(a)
 keys=list(dict.fromkeys(k for r in flat for k in r))
 with (DOC/'whu-formal-results.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(flat)
 with (DOC/'whu-prompt-comparisons.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(pairs[0]));w.writeheader();w.writerows(pairs)
 print(json.dumps({k:v for k,v in result.items() if k!='prompt_by_scale'},indent=2))
if __name__=='__main__':main()

"""Offline P10 metrics. No production threshold changes; no implicit ground truth."""
import numpy as np

def summarize(probability, *, pixel_area, gt=None, valid=None, gt_approved=False):
    p=np.asarray(probability)
    if p.ndim!=2 or not np.isfinite(p).all() or np.any((p<0)|(p>1)):raise ValueError('Invalid probability raster')
    v=np.ones(p.shape,dtype=bool) if valid is None else np.asarray(valid,dtype=bool)
    if v.shape!=p.shape or not v.any():raise ValueError('Invalid valid mask')
    values=p[v]
    result={'prob_mean':float(values.mean()),'prob_std':float(values.std()),'prob_max':float(values.max()),**{f'p{q}':float(np.percentile(values,q)) for q in (90,95,99)},'valid_pixels':int(v.sum())}
    for t in (.3,.5,.7):result[f'fg_ratio@{t}']=float((values>=t).mean())
    result.update(IoU=None,Precision=None,Recall=None,F1=None,false_positive_area=None,gt_status='not_available')
    if gt is not None:
        if not gt_approved:raise ValueError('GT must be explicitly human-approved before scoring')
        truth=np.asarray(gt,dtype=bool)
        if truth.shape!=p.shape:raise ValueError('GT grid mismatch')
        pred=p>=.5;tp=int((pred&truth&v).sum());fp=int((pred&~truth&v).sum());fn=int((~pred&truth&v).sum())
        def ratio(a,b):return a/b if b else None
        result.update(IoU=ratio(tp,tp+fp+fn),Precision=ratio(tp,tp+fp),Recall=ratio(tp,tp+fn),F1=ratio(2*tp,2*tp+fp+fn),false_positive_area=fp*pixel_area,TP=tp,FP=fp,FN=fn,gt_status='human_approved')
    return result

def difference(correct,wrong,valid=None):
    a=np.asarray(correct);b=np.asarray(wrong)
    if a.shape!=b.shape:raise ValueError('Prompt comparison requires identical query grids')
    v=np.ones(a.shape,dtype=bool) if valid is None else np.asarray(valid,dtype=bool)
    return {'mean_wrong_minus_correct':float((b-a)[v].mean()),'mean_absolute_probability_difference':float(np.abs(b-a)[v].mean()),'foreground_ratio_difference@0.5':float(((b>=.5).astype(float)-(a>=.5))[v].mean()),'spatial_binary_disagreement@0.5':float(((a>=.5)!=(b>=.5))[v].mean())}

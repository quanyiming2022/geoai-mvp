import numpy as np
from metrics import summarize,difference

def test_mask_exclusion_and_empty_ground_truth():
 p=np.array([[.9,.9],[.1,.1]]);gt=np.array([[1,0],[1,0]]);valid=np.array([[1,0],[1,1]],dtype=bool)
 r=summarize(p,pixel_area=4,gt=gt,valid=valid,gt_approved=True)
 assert (r['TP'],r['FP'],r['FN'])==(1,0,1)
 assert r['Precision']==1 and r['Recall']==.5 and r['F1']==2/3 and r['IoU']==.5
 z=summarize(np.zeros((2,2)),pixel_area=1,gt=np.zeros((2,2)),gt_approved=True)
 assert z['F1'] is None and z['IoU'] is None

def test_difference_sign_and_spatial_disagreement():
 a=np.array([[.8,.8],[.2,.2]]);b=np.array([[.2,.2],[.8,.8]])
 r=difference(a,b)
 assert abs(r['mean_absolute_probability_difference']-.6)<1e-10
 assert r['spatial_binary_disagreement@0.5']==1
 assert r['foreground_ratio_difference@0.5']==0

import numpy as np
import pytest
from metrics import summarize,difference

def test_no_gt_no_fabricated_accuracy():
 r=summarize(np.array([[.1,.9]]),pixel_area=4)
 assert r['F1'] is None and r['IoU'] is None and r['false_positive_area'] is None

def test_real_counts_and_area():
 p=np.array([[.8,.7],[.6,.2]]);gt=np.array([[1,0],[1,1]])
 r=summarize(p,pixel_area=4,gt=gt,gt_approved=True)
 assert (r['TP'],r['FP'],r['FN'])==(2,1,1)
 assert r['IoU']==.5 and r['F1']==pytest.approx(2/3) and r['false_positive_area']==4

def test_empty_negative_not_fake_perfect_score():
 r=summarize(np.zeros((2,2)),pixel_area=1,gt=np.zeros((2,2)),gt_approved=True)
 assert r['IoU'] is None and r['F1'] is None and r['false_positive_area']==0

def test_draft_gt_rejected():
 with pytest.raises(ValueError):summarize(np.zeros((2,2)),pixel_area=1,gt=np.zeros((2,2)))

def test_prompt_difference_spatial():
 r=difference(np.array([[0.,1.]]),np.array([[1.,0.]]))
 assert r['mean_wrong_minus_correct']==0 and r['spatial_binary_disagreement@0.5']==1

import importlib.util
from pathlib import Path
import numpy as np


def test_remote_research_layout_has_no_query_ground_truth_and_no_resize():
    path=Path(__file__).resolve().parents[2]/'model-worker/research_adapter.py'
    spec=importlib.util.spec_from_file_location('remote_research',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    support=np.full((3,512,512),100,dtype='uint8')
    query=np.full_like(support,200)
    mask=np.zeros((1,512,512),dtype='uint8')
    mask[:,5:20,10:30]=1
    image,annotation,hide=module.composite_inputs(support,mask,query)
    mean=np.array([.485,.456,.406])[:,None,None]
    std=np.array([.229,.224,.225])[:,None,None]
    assert image.shape==(3,1024,512)
    assert np.allclose((image[:,:512]*std+mean)*255,100,atol=.0001)
    assert np.allclose((image[:,512:]*std+mean)*255,200,atol=.0001)
    assert np.allclose(annotation[:,512:]*std+mean,0,atol=1e-6)
    assert (hide[:4]==0).all() and (hide[4:]==1).all()

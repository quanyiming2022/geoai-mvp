import json,os,sys
from pathlib import Path
import numpy as np
import torch
from research_adapter import ResearchSkySensePPAdapter,composite_inputs
from geoai.worker_contract import ModelWorkerRequest
adapter=ResearchSkySensePPAdapter()
assert adapter.predictor is not None
from lib.datasets.utils.pair_trainsforms import Normalize
from lib.datasets.utils.dataset_colors import modal_norm_dict
request=ModelWorkerRequest.model_validate_json(Path(sys.argv[1]).read_text())
support=request.support_image.pixels(); mask=request.support_mask.pixels(); query=request.query_image.pixels()
image,annotation,hide=composite_inputs(support,mask,query)
normalizer=Normalize()
def normalize(rgb,mask):
 return normalizer('flood3i',torch.tensor(rgb),torch.zeros(10,1,16,16),torch.zeros(2,1,16,16),torch.tensor(np.repeat(mask,3,axis=0)*255))
s=normalize(support,mask);q=normalize(query,np.zeros_like(mask))
ref_image=torch.cat((s[0],q[0]),dim=1).numpy();ref_annotation=torch.cat((s[3],q[3]),dim=1).numpy()
assert np.array_equal(ref_image,image)
assert np.array_equal(ref_annotation,annotation)
records=[]
def inspect_output(module,args,output):
 mapping=output['idx_2_color'];slot=[int(k) for k,v in mapping.items() if int(v)>0][0]
 logits=output['logits_hr'][0,:,512:,:].float();prob=logits.softmax(0);argmax=logits.argmax(0)
 records.append({'mapping':mapping,'logit_shape':list(output['logits_hr'].shape),'argmax_foreground_ratio':float((argmax==slot).float().mean()),'unmapped_argmax_ratio':float(((argmax!=0)&(argmax!=slot)).float().mean()),'unused_slot_probability_mass_mean':float((1-prob[0]-prob[slot]).mean())})
hook=adapter.predictor.model.register_forward_hook(inspect_output)
a=adapter.infer(request).probabilities(); b=adapter.infer(request).probabilities()
assert np.array_equal(a,b)
def normalize_missing(module,args):
 sample=args[0]
 for role in ('s1','s2'):
  mean=torch.tensor(modal_norm_dict[role]['mean'],device=sample[role+'_img'].device).reshape(1,-1,1,1,1)
  std=torch.tensor(modal_norm_dict[role]['std'],device=sample[role+'_img'].device).reshape(1,-1,1,1,1)
  sample[role+'_img']=(sample[role+'_img']-mean)/std
pre=adapter.predictor.model.register_forward_pre_hook(normalize_missing)
c=adapter.infer(request).probabilities();pre.remove();hook.remove()
report={'normalization_rgb_exact':True,'normalization_annotation_exact':True,'deterministic_repeat_exact':True,'missing_modality_normalization_max_abs_difference':float(np.abs(a-c).max()),'outputs':records,'note':'Diagnostic only. Does not change the production adapter, seed, inputs or threshold.'}
Path(sys.argv[2]).write_text(json.dumps(report,indent=2));print('AUDIT_RESULT',json.dumps(report))

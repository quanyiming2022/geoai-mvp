import json
import os
from research_adapter import ResearchSkySensePPAdapter

adapter = ResearchSkySensePPAdapter.__new__(ResearchSkySensePPAdapter)
adapter.predictor = None
adapter.torch = None
adapter.checkpoint_digest = None
adapter.version = os.environ['SKYSENSE_MODEL_VERSION']
adapter._load()
assert adapter.predictor is not None, 'Model did not load'
torch = adapter.torch
checkpoint = torch.load(os.environ['SKYSENSE_CHECKPOINT'], map_location='cpu', weights_only=True)
state = checkpoint.get('model', checkpoint)
mapped = {}
for key, value in state.items():
    key = key.replace('fa_history', 'fa_context')
    if key.startswith('module.'):
        key = key[len('module.'):]
    key = key.replace('.Wqkv.', '.in_proj_')
    mapped[key] = value
model = adapter.predictor.model
model = model.module if hasattr(model, 'module') else model
actual = model.state_dict()
missing = sorted(set(actual) - set(mapped))
unexpected = sorted(set(mapped) - set(actual))
mismatched = [key for key in mapped if key in actual and mapped[key].shape != actual[key].shape]
report = {'health': adapter.healthcheck(), 'model_info': adapter.model_info(), 'model_tensor_count': len(actual), 'checkpoint_tensor_count': len(mapped), 'missing': missing, 'unexpected': unexpected, 'shape_mismatches': mismatched}
print(json.dumps(report, ensure_ascii=False), flush=True)
assert not missing and not unexpected and not mismatched, 'Checkpoint coverage requires review'
print('CHECKPOINT_COVERAGE_PASS', flush=True)

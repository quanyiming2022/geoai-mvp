"""Analyze frozen probabilities without rerunning inference or changing thresholds."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import rasterio


def save_png(path, values):
    data=values[None,:,:] if values.ndim==2 else values.transpose(2,0,1)
    with rasterio.open(path, "w", driver="PNG", width=data.shape[2],height=data.shape[1],count=data.shape[0],dtype="uint8") as ds:
        ds.write(data)


def analyze(root, output):
    output.mkdir(parents=True, exist_ok=False)
    report = {}
    arrays = {}
    for case in sorted(root.iterdir()):
        if not (case/'probability.npy').exists():
            continue
        probability = np.load(case/'probability.npy')
        metrics = json.loads((case/'metrics.json').read_text())
        with rasterio.open(case/'query.png') as ds:
            query = ds.read()[:3].transpose(1,2,0)
        destination = output/case.name
        destination.mkdir()
        result = {'probability_sha256': hashlib.sha256((case/'probability.npy').read_bytes()).hexdigest(),
                  'probability_mean':float(probability.mean()), 'probability_std':float(probability.std()),
                  'probability_max':float(probability.max()),
                  **{f'probability_p{p}':float(np.percentile(probability,p)) for p in (50,90,95,99)},
                  'thresholds':{}, 'runtime_ms':metrics['runtime_ms'],
                  'peak_gpu_memory_mb':metrics['gpu_memory_peak']/1024**2}
        for threshold in (.3,.5,.7):
            binary=probability>=threshold
            result['thresholds'][str(threshold)]={'foreground_ratio':float(binary.mean()),'pixels':int(binary.sum())}
            save_png(destination/f'mask-{threshold}.png',binary.astype('uint8')*255)
            overlay=query.copy()
            overlay[binary]=(query[binary]*.55+np.array([255,40,40])*.45).astype('uint8')
            save_png(destination/f'overlay-{threshold}.png',overlay)
        report[case.name]=result
        arrays[case.name]=probability
    b=arrays['B-same-scene-different-tile'];d=arrays['D-wrong-prompt']
    delta=d-b
    np.save(output/'wrong-minus-correct-probability.npy',delta)
    delta_image=np.zeros((*delta.shape,3),dtype='uint8')
    delta_image[:,:,0]=(np.clip(delta,0,1)*255).astype('uint8')
    delta_image[:,:,2]=(np.clip(-delta,0,1)*255).astype('uint8')
    save_png(output/'wrong-minus-correct-probability.png',delta_image)
    report['B_vs_D']={'definition':'D minus B; red positive, blue negative',
                       'mean_delta':float(delta.mean()),'mean_absolute_delta':float(np.abs(delta).mean()),
                       'thresholds':{str(t):{'foreground_ratio_delta':float((d>=t).mean()-(b>=t).mean()),
                                            'spatial_disagreement_ratio':float(np.mean((d>=t)!=(b>=t)))} for t in (.3,.5,.7)}}
    (output/'analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    analyze(args.root,args.output)

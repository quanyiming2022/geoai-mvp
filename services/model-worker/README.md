# Remote research Worker — GPU validation pending

This is an opt-in, research-only adapter bridge, not a verified GPU image or a commercial model. Mac GeoAI continues to run without this service. No weights or upstream source are redistributed.

The adapter follows official SkySense++ source at exact commit `cb0c6b774471ad3314354041c8fa6aae7d49a9bb`: support above query, ImageNet normalization, hidden query annotation, reset seeded temporary vocabulary, and extraction of the foreground slot's probability from the query half. It does not read Flood3i samples or require query ground truth. Upstream predictor construction currently imports its research framework; all those imports are confined to this remote process. Web/API never import this adapter.

## Required preparation on Linux / NVIDIA

1. Obtain and review the official source and research-only checkpoint terms: https://github.com/kang-wu/SkySensePlusPlus . Checkout the exact commit above.
2. Prepare a CUDA environment capable of loading the official checkpoint and compiled dependencies. The upstream README lists Python 3.8 / Torch 1.13.1 / MMCV 1.7.1; this bridge's shared contract requires Python 3.10+ and Pydantic 2. **The combined runtime has not been validated on GPU.** Select compatible Torch/MMCV/CUDA and HTTP dependencies, then pin the working runtime and container digest after actual Linux verification. Do not assume the Mac platform dependency lock is a CUDA environment.
3. Install the shared HTTP contract dependencies (FastAPI, Uvicorn, Pydantic 2, NumPy, Rasterio) in that compatible environment. Do not install the platform database credentials or copy its `.env`.
4. Mount the GeoAI source and official source read-only. Store the following non-secret configuration on the remote server, with any future credentials only in ignored server `.env`:

```bash
export SKYSENSE_SOURCE=/absolute/path/to/SkySensePlusPlus
export SKYSENSE_CHECKPOINT=/absolute/path/to/actual-checkpoint
export SKYSENSE_CHECKPOINT_SHA256=actual_64_character_sha256
export SKYSENSE_MODEL_VERSION=your_verified_release_version
export PYTHONPATH=/absolute/path/to/geoai-mvp/services/api:/absolute/path/to/geoai-mvp/services/model-worker
python -m uvicorn server:app --host 0.0.0.0 --port 8001 --workers 1
```

All adapter state is serialized per process. Keep one process per loaded GPU model; worker concurrency is bounded and busy requests are rejected. Cancellation rejects late output, but cannot forcibly interrupt a running CUDA kernel. The platform's attempt/configuration fencing remains authoritative.

If loading fails, `/health` remains reachable with `model_loaded=false`; no dummy prediction is substituted. `/model-info` reports `usage_policy=research_only`. Configure the exact same model name (`SkySense++`), version and checkpoint digest in Mac Models & Compute, then register the actual LAN URL and Test Connection.

## Pending acceptance

The NumPy-only layout test runs locally; loading, CUDA determinism, slot mapping against a real checkpoint, latency, peak VRAM, and three actual image fixtures are **unverified**. Current strict deterministic mode may reject unsupported GPU operations; diagnose instead of silently disabling it. Three fixtures must include support=query, same-class different query and unrelated query, with probability distribution and foreground metrics inspected. No AOI tiling/stitching is implemented.

## GPU host deployment archive

See [GPU server installation and offline transfer runbook](../../docs/gpu-server-deployment.md) for the executed host installer, verified container GPU checks, source staging scripts, and remaining runtime/checkpoint gates. The current acceptance requires four fixtures, including wrong-prompt; follow [P9B acceptance gates](../../docs/p9b-acceptance-gates.md).

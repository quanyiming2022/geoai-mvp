#!/usr/bin/env bash
# Run on the GPU host after loading the official linux/amd64 Ubuntu image.
set -euo pipefail
geoai_device=${1:?Usage: bash verify-gpu-container.sh GPU_INDEX_OR_UUID}
[[ "$geoai_device" =~ ^[0-9]+$ || "$geoai_device" =~ ^GPU-[a-fA-F0-9-]+$ ]] || { echo 'Invalid GPU device' >&2; exit 1; }
docker version --format '{{.Server.Version}}'
docker compose version
nvidia-ctk --version
nvidia-smi
[[ $(docker image inspect ubuntu:24.04 --format '{{.Os}}/{{.Architecture}}') == linux/amd64 ]] || { echo 'Expected linux/amd64 Ubuntu image' >&2; exit 1; }
docker run --rm --pull=never --gpus "device=$geoai_device" ubuntu:24.04 nvidia-smi

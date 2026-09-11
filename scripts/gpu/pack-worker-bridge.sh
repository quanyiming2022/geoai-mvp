#!/usr/bin/env bash
# Package only the current HTTP bridge source; no environment files or weights.
set -euo pipefail
geoai_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
geoai_output=${1:?Usage: bash pack-worker-bridge.sh /absolute/path/worker-bridge.tar.gz}
[[ "$geoai_output" == /* && ! -e "$geoai_output" ]] || { echo 'Use a new absolute output path' >&2; exit 1; }
export COPYFILE_DISABLE=1
tar --no-xattrs -czf "$geoai_output" -C "$geoai_root" \
  services/model-worker/server.py \
  services/model-worker/research_adapter.py \
  services/api/geoai/__init__.py \
  services/api/geoai/model_worker.py \
  services/api/geoai/worker_contract.py \
  services/api/geoai/fake_real_adapter.py
shasum -a 256 "$geoai_output"

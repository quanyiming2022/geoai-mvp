#!/bin/sh
set -eu
GEOAI_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec docker compose --project-name geoai-mvp --env-file "$GEOAI_ROOT/.env"   -f "$GEOAI_ROOT/infra/supabase/upstream/docker-compose.yml"   -f "$GEOAI_ROOT/infra/docker-compose.geoai.yml" "$@"

#!/usr/bin/env bash
# This public runtime is independent of the locally recovered manager image.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export COOP_KIT_ROOT="$ROOT"
if [[ -z "${EVEREST_RUNTIME_IMAGE:-}" ]]; then
  EVEREST_RUNTIME_IMAGE="$(python3 - "$ROOT/IMAGES.lock.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
if not p.is_file(): raise SystemExit('IMAGES.lock.json missing; set EVEREST_RUNTIME_IMAGE explicitly for a local build.')
d=json.loads(p.read_text()); image=d['everest_runtime']
if '@sha256:' not in image: raise SystemExit('Published runtime must be pinned by registry digest.')
print(image)
PY
)"
fi
export EVEREST_RUNTIME_IMAGE
mkdir -p "$ROOT/diagnostics/clean-everest"
COMPOSE=(docker compose --project-name coop-everest-clean --project-directory "$ROOT" -f "$ROOT/deploy/everest.clean.yml")
case "${1:-status}" in
  config) "${COMPOSE[@]}" config --quiet;;
  pull) "${COMPOSE[@]}" pull;;
  up) "${COMPOSE[@]}" up -d --wait --wait-timeout 240;;
  stop) "${COMPOSE[@]}" stop;;
  status|ps) "${COMPOSE[@]}" ps;;
  logs) tail -n "${2:-100}" "$ROOT/diagnostics/clean-everest/manager.log";;
  start-session)
    "${COMPOSE[@]}" exec -T mqtt-server mosquitto_pub -h 127.0.0.1 -q 1 -t everest_external/nodered/1/carsim/cmd/execute_charging_session -m 'sleep 1;iso_wait_slac_matched;iso_start_v2g_session ac,-1,-1;iso_wait_pwr_ready;iso_draw_power_regulated 16,3;sleep 36000';;
  stop-session)
    "${COMPOSE[@]}" exec -T mqtt-server mosquitto_pub -h 127.0.0.1 -q 1 -t everest_external/nodered/1/carsim/cmd/modify_charging_session -m 'iso_stop_charging;iso_wait_v2g_session_stopped;unplug';;
  exec) shift; "${COMPOSE[@]}" exec -T manager "$@";;
  *) echo 'Usage: clean_everest.sh {config|pull|up|stop|status|logs|start-session|stop-session|exec COMMAND...}' >&2; exit 2;;
esac

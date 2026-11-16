#!/usr/bin/env bash
# Resume this PC's preserved lab; never build, seed, or regenerate certificates.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/check_host_memory.py
exec 9>"$ROOT/diagnostics/local-review.lock"
flock -n 9 || { echo 'Another local review is already running.' >&2; exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$ROOT/diagnostics/local-review-$stamp"
mkdir -p "$out"
echo "Review output: $out"
bash scripts/stack.sh config
bash scripts/everest_citrine.sh config
# Preserve the configured runtime before creating the local project. This image
# contains laboratory private keys and must remain local to this PC.
if ! docker image inspect ev-pnc/manager:coop-local-20261116 >/dev/null 2>&1; then
  state="$(docker inspect --format '{{.State.Status}}' coop-everest-citrine-manager-1)"
  [[ "$state" == exited ]] || { echo 'Stop the previous EVerest session before creating the local runtime snapshot.' >&2; exit 1; }
  docker commit coop-everest-citrine-manager-1 ev-pnc/manager:coop-local-20261116
fi
# Start existing backend containers in dependency order without triggering builds.
docker start coop-sil-billing-ocpp-db-1 coop-sil-billing-amqp-broker-1
for name in ocpp-db amqp-broker; do
  ready=false
  for ((n=0;n<120;n++)); do
    if [[ "$(docker inspect --format '{{.State.Health.Status}}' "coop-sil-billing-$name-1")" == healthy ]]; then ready=true; break; fi
    sleep 1
  done
  $ready || { echo "$name did not become healthy" >&2; exit 1; }
done
docker start coop-sil-billing-graphql-engine-1 coop-sil-billing-citrine-1 coop-sil-billing-mock-msp-1 coop-sil-billing-citrineos-ocpi-1 coop-sil-billing-billing-1
ready=false
for ((n=0;n<90;n++)); do
  if python3 scripts/verify_backend.py --require services --out "$out/services.json"; then ready=true; break; fi
  sleep 2
done
$ready || { echo 'Backend readiness timed out.' >&2; exit 1; }
# Old containers remain available for recovery; stop them to release host ports.
docker stop coop-everest-citrine-manager-1 coop-everest-citrine-nodered-1 coop-everest-citrine-mqtt-server-1
bash scripts/everest_citrine.sh up
bash scripts/everest_citrine.sh configure
bash scripts/everest_citrine.sh start
ready=false
for ((n=0;n<60;n++)); do
  if grep -q 'Received BootNotificationResponse' diagnostics/everest-session/manager.log; then ready=true; break; fi
  sleep 1
done
$ready || { echo 'No new BootNotification response.' >&2; exit 1; }
since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$since" > "$out/since.txt"
session_started=false
cleanup() { if $session_started; then bash scripts/everest_citrine.sh stop-session || true; fi; }
trap cleanup EXIT
bash scripts/everest_citrine.sh start-session
session_started=true
sleep "${REVIEW_CHARGE_SECONDS:-45}"
bash scripts/everest_citrine.sh stop-session
session_started=false
sleep 12
passed=false
for ((n=0;n<6;n++)); do
  if python3 scripts/verify_backend.py --require delivery --sync --since "$since" --out "$out/delivery.json"; then passed=true; break; fi
  sleep 5
done
$passed || { echo 'Delivery verification failed. See delivery.json and manager log.' >&2; exit 1; }
python3 scripts/collect_evidence.py --include-wire
cp diagnostics/everest-session/manager.log "$out/manager.log"
python3 scripts/review_result.py "$out"
echo 'Data chain and separate PnC evidence checks passed.'
echo "Result: $out/delivery.json"

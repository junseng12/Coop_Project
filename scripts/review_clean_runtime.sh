#!/usr/bin/env bash
# Validate a new session from the clean runtime against the existing lab backend.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec 9>"$ROOT/diagnostics/clean-review.lock"
flock -n 9 || { echo 'Another clean-runtime review is running' >&2; exit 1; }
out="$ROOT/diagnostics/clean-review-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
python3 scripts/verify_backend.py --require services --out "$out/services.json"
bash scripts/clean_everest.sh up
since="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$since" > "$out/since.txt"
active=false
cleanup() { if $active; then bash scripts/clean_everest.sh stop-session || true; fi; }
trap cleanup EXIT
bash scripts/clean_everest.sh start-session
active=true
sleep "${REVIEW_CHARGE_SECONDS:-45}"
bash scripts/clean_everest.sh stop-session
active=false
sleep 12
ok=false
for ((n=0;n<6;n++)); do
 if python3 scripts/verify_backend.py --require delivery --sync --since "$since" --out "$out/delivery.json"; then ok=true; break; fi
 sleep 5
done
$ok || exit 1
cp diagnostics/clean-everest/manager.log "$out/manager.log"
python3 scripts/review_result.py "$out" --manager coop-everest-clean-manager-1 --runtime-config /state/everest.yaml
python3 scripts/collect_evidence.py --include-wire
printf 'Clean runtime E2E passed. Result: %s/result.html\n' "$out"

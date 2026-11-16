#!/usr/bin/env bash
# Run from WSL/Ubuntu. All writes stay in this kit and its isolated stack.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="${1:-audit}"
case "$MODE" in audit|backend|check) ;; *) echo 'Usage: bash scripts/run_local.sh {audit|backend|check} [existing-EVerest-root]' >&2; exit 2;; esac
EXISTING="${2:-${EV_PNC_ROOT:-$HOME/research/ev-pnc}}"
if [[ ! -d "$EXISTING" && -d /home/hyebin/research/ev-pnc ]]; then EXISTING=/home/hyebin/research/ev-pnc; fi
command -v python3 >/dev/null || { echo 'Python 3.10+ is required inside WSL.' >&2; exit 2; }
mkdir -p diagnostics
bash scripts/audit_from_wsl.sh "$EXISTING" "$ROOT/diagnostics/local-audit.json"
if [[ "$MODE" == audit ]]; then
  echo 'Audit saved. Existing EVerest was not modified or started.'
  exit 0
fi
if ! command -v docker >/dev/null || ! docker info >/dev/null 2>&1; then
  echo 'BLOCKED: Docker Engine is not accessible from this WSL distribution.' >&2
  echo 'Existing files/containers preserved. Review diagnostics/local-audit.json.' >&2
  exit 2
fi
if [[ "$MODE" == backend ]]; then
  python3 scripts/init_env.py
  python3 scripts/prepare_upstream.py
  bash scripts/stack.sh config
  bash scripts/stack.sh up
  bash scripts/stack.sh seed
  python3 scripts/verify_backend.py --require services
  echo 'Backend ready only. Connect and run the existing EVerest PnC session before check.'
else
  python3 scripts/verify_backend.py --require delivery --sync
fi


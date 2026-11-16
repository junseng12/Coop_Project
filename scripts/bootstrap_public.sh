#!/usr/bin/env bash
# First-time public-source setup. Existing DB volumes are never reseeded blindly.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null
command -v git >/dev/null
python3 --version
docker info >/dev/null
if [[ -x /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe ]]; then
  python3 scripts/check_host_memory.py
fi
python3 scripts/init_env.py
python3 scripts/prepare_upstream.py
fresh=false
if ! docker volume inspect coop-sil-billing_coop-db >/dev/null 2>&1; then fresh=true; fi
bash scripts/stack.sh up
if $fresh; then
  bash scripts/stack.sh seed
else
  echo 'Existing DB volume preserved; initial seed skipped.'
fi
python3 scripts/verify_backend.py --require services --out diagnostics/public-services.json
bash scripts/clean_everest.sh pull
bash scripts/clean_everest.sh up
echo 'Public runtime ready. Use clean_everest.sh start-session / stop-session.'

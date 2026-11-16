#!/usr/bin/env bash
# Run from the existing EVerest VS Code WSL terminal. Read-only except output report.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ARGS=(--root "${1:-$PWD}" --out "${2:-$HOME/coop-local-audit.json}")
if command -v powershell.exe >/dev/null 2>&1 && command -v wslpath >/dev/null 2>&1; then
  WIN_APPDATA="$(powershell.exe -NoProfile -NonInteractive -Command '$env:APPDATA' 2>/dev/null | tr -d '\r')"
  if [[ -n "$WIN_APPDATA" ]]; then
    VSCODE_STATE="$(wslpath "$WIN_APPDATA")/Code/User/globalStorage/state.vscdb"
    [[ ! -f "$VSCODE_STATE" ]] || ARGS+=(--vscode-state "$VSCODE_STATE")
  fi
fi
python3 "$ROOT/scripts/audit_local.py" "${ARGS[@]}"

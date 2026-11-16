#!/usr/bin/env bash
# systemd owns the job, so closing VS Code or its terminal does not kill it.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/diagnostics/jobs"
if [[ $# -eq 0 ]]; then
  echo 'Usage: bash scripts/detached.sh COMMAND [ARG ...]' >&2
  exit 2
fi
job="coop-job-$(date -u +%Y%m%dT%H%M%S)-$$"
out="$ROOT/diagnostics/jobs/$job"
mkdir "$out"
printf '%q ' "$@" > "$out/command.txt"
printf '\n' >> "$out/command.txt"
systemd-run --user --unit="$job" --collect --working-directory="$ROOT" \
  --property="StandardOutput=append:$out/output.log" \
  --property="StandardError=append:$out/output.log" \
  /bin/bash -c 'out=$1; shift; printf "RUNNING\n" > "$out/status.txt"; "$@"; rc=$?; printf "EXIT_CODE=%s\n" "$rc" > "$out/status.txt"; exit "$rc"' bash "$out" "$@"
echo "Job: $job"
echo "Log: $out/output.log"
echo "Status: $out/status.txt"
echo 'Survives VS Code closing; does not survive WSL shutdown or Windows restart.'

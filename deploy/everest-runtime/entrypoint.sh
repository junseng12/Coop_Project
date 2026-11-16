#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-run}" != run ]]; then exec "$@"; fi
python3 /usr/local/bin/coop-initialize.py > /evidence/initialize.log 2>&1 || { tail -60 /evidence/initialize.log; exit 1; }
openssl ocsp -index /state/ocsp/index.txt -port 8888 \
  -rsigner /state/certs/ca/mo/MO_SUB_CA2.pem \
  -rkey /state/certs/client/mo/MO_SUB_CA2.key \
  -passin file:/state/certs/client/mo/MO_SUB_CA2_LEAF_PASSWORD.txt \
  -CA /state/certs/ca/mo/MO_SUB_CA2.pem \
  -nrequest 100000 > /evidence/ocsp-responder.log 2>&1 &
ocsp_pid=$!
manager --prefix /ext/dist --conf /state/everest.yaml > /evidence/manager.log 2>&1 &
manager_pid=$!
cleanup() { kill -TERM "$manager_pid" "$ocsp_pid" 2>/dev/null || true; wait "$manager_pid" "$ocsp_pid" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
wait -n "$manager_pid" "$ocsp_pid"

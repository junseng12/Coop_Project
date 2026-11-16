#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

PKI_ARCHIVE="${EVEREST_PKI_ARCHIVE:-$ROOT/diagnostics/private-pki/renewed-test-certs.tar}"

export COOP_KIT_ROOT="$ROOT"
export TAG="${TAG:-2025.10.0-single-phase}"
export EVEREST_MANAGER_CPUS="${EVEREST_MANAGER_CPUS:-4}"
export EVEREST_MANAGER_MEMORY="${EVEREST_MANAGER_MEMORY:-6G}"
mkdir -p "$ROOT/diagnostics/everest-session/session-logs"
COMPOSE=(docker compose --project-name coop-everest-local --project-directory "$ROOT" -f "$ROOT/deploy/everest.local.yml")
ACTION="${1:-ps}"
case "$ACTION" in
  config)
    "${COMPOSE[@]}" config --quiet
    echo 'EVerest/Citrine Compose syntax validation passed.'
    ;;
  up)
    "${COMPOSE[@]}" config --quiet
    "${COMPOSE[@]}" up -d --no-build
    ;;
  configure)
    [[ -f "$PKI_ARCHIVE" ]] || { echo 'Run: bash scripts/everest_citrine.sh generate-pki' >&2; exit 1; }
    grep -q 'verify_contract_cert_chain: true' "$ROOT/config/config-sil-ocpp201-pnc-strict.yaml"
    "${COMPOSE[@]}" exec -T manager sh -ec 'cp /tmp/config-sil-ocpp201-pnc.yaml /ext/source/config/config-sil-ocpp201-pnc.yaml'
    "${COMPOSE[@]}" exec -T manager tar -C /ext/dist/etc/everest -xf - < "$PKI_ARCHIVE"
    "${COMPOSE[@]}" exec -T manager sh -ec 'cp -a /ext/dist/etc/everest/certs/. /ext/source/config/certs/; grep -q "ws://citrine:8081/cp001" /ext/dist/share/everest/modules/OCPP201/component_config/standardized/InternalCtrlr.json'
    ;;
  generate-pki)
    "${COMPOSE[@]}" exec -T manager sh -lc "pkill -x manager 2>/dev/null || true"
    "${COMPOSE[@]}" exec -T manager sh -lc "pkill -x openssl 2>/dev/null || true"
    "${COMPOSE[@]}" exec -T manager sh -ec \
      "cd /ext/dist/libexec/everest/3rd_party/josev/iso15118/shared/pki; \
       sed -i 's/^commonName.*/commonName = NL123C10028948M/' configs/contractLeafCert.cnf; \
       sed -i 's#^authorityInfoAccess.*#authorityInfoAccess = OCSP;URI:http://manager:8888/#' configs/contractLeafCert.cnf; \
       sed -i '/^authorityInfoAccess/d' configs/moRootCACert.cnf configs/moSubCA1Cert.cnf configs/moSubCA2Cert.cnf; \
       sh ./create_certs.sh -v iso-2 -i /ext/source >/evidence/pki-generation.log 2>&1; \
       cp -a /ext/source/config/certs/. /ext/dist/etc/everest/certs/; \
       openssl verify -CAfile /ext/dist/etc/everest/certs/ca/v2g/V2G_ROOT_CA.pem \
         -untrusted /ext/dist/etc/everest/certs/ca/csms/CPO_SUB_CA1.pem \
         -untrusted /ext/dist/etc/everest/certs/ca/csms/CPO_SUB_CA2.pem \
         /ext/dist/etc/everest/certs/client/cso/SECC_LEAF.pem; \
       openssl verify -CAfile /ext/dist/etc/everest/certs/ca/mo/MO_ROOT_CA.pem \
         -untrusted /ext/dist/etc/everest/certs/ca/mo/MO_SUB_CA1.pem \
         -untrusted /ext/dist/etc/everest/certs/ca/mo/MO_SUB_CA2.pem \
         /ext/dist/etc/everest/certs/client/mo/MO_LEAF.pem"
    "${COMPOSE[@]}" exec -T manager sh -ec \
      "mkdir -p /evidence/ocsp; \
       expiry=\$(openssl x509 -in /ext/dist/etc/everest/certs/client/mo/MO_LEAF.pem -noout -enddate | cut -d= -f2); \
       expiry=\$(date -u -d \"\$expiry\" +%y%m%d%H%M%SZ); \
       serial=\$(openssl x509 -in /ext/dist/etc/everest/certs/client/mo/MO_LEAF.pem -noout -serial | cut -d= -f2); \
       printf 'V\\t%s\\t\\t%s\\tunknown\\t/CN=NL123C10028948M\\n' \"\$expiry\" \"\$serial\" > /evidence/ocsp/index.txt"
    mkdir -p "$(dirname "$PKI_ARCHIVE")"
    "${COMPOSE[@]}" exec -T manager tar -C /ext/dist/etc/everest -cf - certs > "$PKI_ARCHIVE"
    chmod 600 "$PKI_ARCHIVE"
    {
      "${COMPOSE[@]}" exec -T manager openssl x509 -inform DER -in /ext/dist/etc/everest/certs/client/mo/MO_LEAF.der -noout -subject -issuer -dates -fingerprint -sha256
      "${COMPOSE[@]}" exec -T manager openssl x509 -in /ext/dist/etc/everest/certs/client/cso/SECC_LEAF.pem -noout -subject -issuer -dates -fingerprint -sha256
      sha256sum "$PKI_ARCHIVE"
    } | tee "$ROOT/diagnostics/everest-session/pki-public-evidence.txt"
    ;;
  stop) "${COMPOSE[@]}" stop;;
  start)
    "${COMPOSE[@]}" up -d --no-build
    if ! "${COMPOSE[@]}" exec -T manager sh -lc "pgrep -x openssl >/dev/null"; then
      "${COMPOSE[@]}" exec -T -d manager sh -lc \
        "exec openssl ocsp -index /evidence/ocsp/index.txt -port 8888 \
          -rsigner /ext/dist/etc/everest/certs/ca/mo/MO_SUB_CA2.pem \
          -rkey /ext/dist/etc/everest/certs/client/mo/MO_SUB_CA2.key \
          -passin file:/ext/dist/etc/everest/certs/client/mo/MO_SUB_CA2_LEAF_PASSWORD.txt \
          -CA /ext/dist/etc/everest/certs/ca/mo/MO_SUB_CA2.pem \
          -nrequest 1000 > /evidence/ocsp-responder.log 2>&1"
    fi
    if "${COMPOSE[@]}" exec -T manager sh -lc "pgrep -x manager >/dev/null"; then
      echo 'EVerest manager is already running.'
    else
      "${COMPOSE[@]}" exec -T -d manager sh -lc \
        "exec /ext/build/run-scripts/run-sil-ocpp201-pnc.sh > /evidence/manager.log 2>&1"
    fi
    ;;
  start-session)
    "${COMPOSE[@]}" exec -T mqtt-server mosquitto_pub -h 127.0.0.1 -q 1 \
      -t everest_external/nodered/1/carsim/cmd/execute_charging_session \
      -m 'sleep 1;iso_wait_slac_matched;iso_start_v2g_session ac,-1,-1;iso_wait_pwr_ready;iso_draw_power_regulated 16,3;sleep 36000'
    ;;
  stop-session)
    "${COMPOSE[@]}" exec -T mqtt-server mosquitto_pub -h 127.0.0.1 -q 1 \
      -t everest_external/nodered/1/carsim/cmd/modify_charging_session \
      -m 'iso_stop_charging;iso_wait_v2g_session_stopped;unplug'
    ;;
  ps) "${COMPOSE[@]}" ps;;
  logs) tail -n "${2:-200}" "$ROOT/diagnostics/everest-session/manager.log";;
  down) "${COMPOSE[@]}" down;;
  *) echo 'Usage: bash scripts/everest_citrine.sh {config|up|generate-pki|configure|start|start-session|stop-session|ps|logs [lines]|down}' >&2; exit 2;;
esac

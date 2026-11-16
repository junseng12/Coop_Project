#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export COOP_KIT_ROOT="$ROOT"
VENDOR="$ROOT/vendor/citrineos-core"
[[ -d "$VENDOR/.git" ]] || { echo 'Run: python3 scripts/prepare_upstream.py' >&2; exit 1; }
[[ -f "$ROOT/.env" ]] || { echo 'Run: python3 scripts/init_env.py' >&2; exit 1; }
PIN="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["citrineos_core"]["commit"])' "$ROOT/UPSTREAM.lock.json")"
[[ "$(git -C "$VENDOR" rev-parse HEAD)" == "$PIN" ]] || { echo 'Vendor commit mismatch; refusing to run.' >&2; exit 1; }
VERSION="$(docker compose version --short)"
python3 - "$VERSION" <<'PY'
import re,sys
parts=re.findall(r'\d+',sys.argv[1])
if len(parts)<3 or tuple(map(int,parts[:3])) < (2,24,4):
    raise SystemExit('Docker Compose >=2.24.4 required for !override')
PY
COMPOSE=(docker compose --project-name coop-sil-billing --project-directory "$VENDOR" --env-file "$ROOT/.env" -f "$VENDOR/docker-compose.yml" -f "$VENDOR/docker-compose.local.yml" -f "$ROOT/deploy/citrine.override.yml" --profile ocpi)
ACTION="${1:-config}"
case "$ACTION" in
  config) "${COMPOSE[@]}" config --quiet; echo 'Compose syntax validation passed; no containers started.';;
  up) "${COMPOSE[@]}" config --quiet; "${COMPOSE[@]}" up -d --build --wait --wait-timeout "${COOP_STARTUP_TIMEOUT:-300}";;
  seed)
    # Only this isolated Compose project's new laboratory database is seeded.
    # Slim upstream images do not contain pnpm: use the installed CLI directly.
    "${COMPOSE[@]}" exec -T -e OCPI_ENV=docker citrineos-ocpi ./node_modules/.bin/sequelize-cli db:seed:all --debug
    "${COMPOSE[@]}" exec -T ocpp-db psql -q -U citrine -d citrine -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO "Authorizations"
  ("idToken", "idTokenType", "additionalInfo", "status", "tenantId", "tenantPartnerId", "createdAt", "updatedAt")
VALUES
  ('NL123C10028948M', 'eMAID', '[{"additionalIdToken":"NL123C10028948M","type":"eMAID"},{"additionalIdToken":"CoopLab","type":"issuer"}]'::jsonb,
   'Accepted', 1, 1, NOW(), NOW())
ON CONFLICT ("tenantId", "idToken", "idTokenType") DO UPDATE SET
  "additionalInfo" = EXCLUDED."additionalInfo",
  "status" = EXCLUDED."status",
  "tenantPartnerId" = EXCLUDED."tenantPartnerId",
  "updatedAt" = NOW();

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['Tenants','TenantPartners','Locations','ChargingStations','Tariffs','Evses','Connectors','Authorizations'] LOOP
    EXECUTE format('SELECT setval(pg_get_serial_sequence(%L, ''id''), (SELECT COALESCE(MAX(id), 1) FROM %I))', quote_ident(t), t);
  END LOOP;
END $$;
SQL
    echo 'Seeded the isolated lab DB, including the explicit NL123C10028948M PnC contract mapping; end-to-end delivery is not yet verified.';;
  ps) "${COMPOSE[@]}" ps;;
  logs) "${COMPOSE[@]}" logs --tail=100 "${2:-billing}";;
  down) "${COMPOSE[@]}" down;; # preserves named volumes
  lock-images)
    mkdir -p "$ROOT/diagnostics"
    "${COMPOSE[@]}" images --format json > "$ROOT/diagnostics/compose-images.json"
    ids="$("${COMPOSE[@]}" images -q | sort -u)"
    : > "$ROOT/diagnostics/image-identities.jsonl"
    while IFS= read -r id; do
      [[ -n "$id" ]] || continue
      docker image inspect --format '{{json .Id}} {{json .RepoDigests}} {{json .RepoTags}}' "$id" >> "$ROOT/diagnostics/image-identities.jsonl"
    done <<< "$ids"
    echo 'Saved image identities. Source lock alone is not a full binary lock.';;
  *) echo 'Usage: bash scripts/stack.sh {config|up|seed|ps|logs [service]|down|lock-images}' >&2; exit 2;;
esac

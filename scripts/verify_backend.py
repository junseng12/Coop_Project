#!/usr/bin/env python3
"""Probe real services; correlate CSMS transactions, OCPI CDR pushes and billing.
Does not establish PnC, EVerest origin, reference energy or payment.
Default is read-only; --sync explicitly creates mock billing statements.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from billing.app import extract_cdrs
from billing.engine import sha

def env_values():
    values = {}
    if (ROOT / ".env").is_file():
        for line in (ROOT / ".env").read_text().splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key] = value
    for key in ("BILLING_API_TOKEN", "MOCK_MSP_CONTROL_SECRET"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values

def request_json(url, headers=None, body=None):
    raw = None if body is None else json.dumps(body).encode()
    req = Request(url, data=raw, headers={"Content-Type": "application/json", **(headers or {})})
    with urlopen(req, timeout=15) as response:
        data = response.read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError("Response exceeds size cap")
    return json.loads(data)

def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Missing timestamp")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timezone required")
    return dt

def correlate(cdrs, exchanges, invoices, transactions, station, since=None):
    """Join actual bodies/hashes; stored objects alone cannot pass."""
    since_dt = parse_time(since) if since else None
    results = []
    for cdr in cdrs:
        fingerprint = sha(cdr)
        delivered = False
        for exchange in exchanges:
            if not isinstance(exchange, dict):
                continue
            response = exchange.get("response", {})
            body = response.get("body")
            status = response.get("ocpiStatusCode")
            if status is None and isinstance(body, dict):
                status = body.get("status_code")
            when_ok = True
            if since_dt:
                try:
                    when_ok = parse_time(exchange.get("timing", {}).get("receivedAt")) >= since_dt
                except ValueError:
                    when_ok = False
            candidate = exchange.get("request", {}).get("body")
            if (exchange.get("direction") == "inbound"
                and exchange.get("module") == "cdrs"
                and exchange.get("request", {}).get("method") == "POST"
                and 200 <= response.get("httpStatus", 0) < 300
                and status == 1000
                and exchange.get("validation", {}).get("ok") is True
                and isinstance(candidate, dict)
                and sha(candidate) == fingerprint and when_ok):
                delivered = True
                break
        invoice_ok = any(
            inv.get("cdr_sha256") == fingerprint
            and inv.get("session_id") == cdr.get("session_id")
            and inv.get("source") == "citrine-mock-state-snapshot"
            and inv.get("status") == "SIMULATED_INVOICE_NOT_PAID"
            for inv in invoices)
        # Pinned SessionMapper uses transactionId verbatim as session.id.
        transaction_ok = any(
            tx.get("transactionId") == cdr.get("session_id")
            and str(tx.get("stationId")) == str(station)
            and tx.get("isActive") is False for tx in transactions)
        results.append({
            "cdr_id": cdr.get("id"), "session_id": cdr.get("session_id"),
            "cdr_sha256": fingerprint, "validated_ocpi_push": delivered,
            "completed_csms_transaction": transaction_ok,
            "matching_snapshot_invoice": invoice_ok,
            "data_chain_observed": delivered and transaction_ok and invoice_ok,
        })
    return results

def probe(args):
    values = env_values()
    mh = {"x-mock-control-secret": values.get("MOCK_MSP_CONTROL_SECRET", "")}
    bh = {"Authorization": "Bearer " + values.get("BILLING_API_TOKEN", "")}
    checks, snapshots = [], {}
    endpoints = [
        ("mock_health", args.mock_url + "/_mock/health", mh, None),
        ("billing_health", args.billing_url + "/health", {}, None),
        ("hasura_health", args.hasura_url.rstrip("/").removesuffix("/v1/graphql") + "/healthz", {}, None),
        ("cdrs", args.mock_url + "/_mock/state/cdrs", mh, None),
        ("cdr_wire", args.mock_url + "/_mock/received/cdrs?limit=1000", mh, None),
        ("findings", args.mock_url + "/_mock/findings", mh, None),
        ("csms", args.hasura_url, {}, {"query":
            "{ ChargingStations(order_by:{id:asc},limit:100){id ocppConnectionName isOnline}"
            " Transactions(order_by:{id:desc},limit:1000){transactionId stationId isActive totalKwh}"
            " TenantPartners(where:{partyId:{_eq:\"TST\"}}){id}"
            " Authorizations(where:{idToken:{_eq:\"DEADBEEF\"}}){id}"
            " Locations(where:{id:{_eq:1}}){id} }"}),
    ]
    for name, url, headers, body in endpoints:
        try:
            if name == "hasura_health":
                with urlopen(Request(url), timeout=10) as response:
                    value = {"status_code": response.status}
            else:
                value = request_json(url, headers, body)
            if isinstance(value, dict) and value.get("errors"):
                raise ValueError("GraphQL returned errors")
            snapshots[name] = value
            checks.append({"check": name, "status": "PASS"})
        except Exception as exc:
            checks.append({"check": name, "status": "FAIL", "error_type": type(exc).__name__})
    cdrs = []
    try:
        cdrs = extract_cdrs(snapshots.get("cdrs", {}))
    except ValueError:
        checks.append({"check": "cdr_shape", "status": "FAIL"})
    if args.sync and cdrs and all(x["status"] == "PASS" for x in checks):
        try:
            sync = request_json(args.billing_url + "/api/sync", bh, {})
            checks.append({"check": "billing_sync", "status": "PASS" if sync.get("count", 0) > 0 else "FAIL"})
        except Exception as exc:
            checks.append({"check": "billing_sync", "status": "FAIL", "error_type": type(exc).__name__})
    try:
        snapshots["invoices"] = request_json(args.billing_url + "/api/invoices", bh)
        checks.append({"check": "invoices_api", "status": "PASS"})
    except Exception as exc:
        checks.append({"check": "invoices_api", "status": "FAIL", "error_type": type(exc).__name__})
    csms = snapshots.get("csms", {}).get("data", {})
    observed_station = next((s for s in csms.get("ChargingStations", []) if s.get("ocppConnectionName") == args.station), None)
    seeds_ok = bool(observed_station) and all(csms.get(key) for key in ("TenantPartners", "Authorizations", "Locations"))
    checks.append({"check": "lab_seed_rows", "status": "PASS" if seeds_ok else "FAIL"})
    station_database_id = observed_station.get("id") if observed_station else None
    rows = correlate(cdrs, snapshots.get("cdr_wire", []),
        snapshots.get("invoices", {}).get("invoices", []),
        csms.get("Transactions", []), station_database_id, args.since)
    services_ok = all(c["status"] == "PASS" for c in checks) and bool(checks)
    delivery_ok = services_ok and any(row["data_chain_observed"] for row in rows)
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "gate_requested": args.require,
        "gate_passed": services_ok if args.require == "services" else delivery_ok,
        "status": "DATA_CHAIN_OBSERVED" if delivery_ok else ("SERVICES_REACHABLE_NO_DATA_CHAIN" if services_ok else "BLOCKED"),
        "checks": checks, "station": observed_station,
        "cdr_count": len(cdrs), "correlations": rows,
        "new_pushes_since": args.since, "trace_limit": 1000,
        "truncated_trace_possible": True,
        "pnc_authentication_verified": False,
        "everest_origin_independently_verified": False,
        "reference_energy_verified": False, "payment_executed": False,
        "scope": "API/DB/wire correlation only. PnC needs separate contract-certificate evidence.",
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock-url", default="http://127.0.0.1:18083")
    parser.add_argument("--billing-url", default="http://127.0.0.1:18088")
    parser.add_argument("--hasura-url", default="http://127.0.0.1:18090/v1/graphql")
    parser.add_argument("--station", default="cp001")
    parser.add_argument("--since", help="ISO8601 timestamp; reject older push evidence")
    parser.add_argument("--require", choices=["services", "delivery"], default="delivery")
    parser.add_argument("--sync", action="store_true", help="Create mock bills from received CDRs")
    parser.add_argument("--out", default=str(ROOT / "diagnostics/backend-verification.json"))
    args = parser.parse_args()
    if args.since:
        parse_time(args.since)
    try:
        report = probe(args)
    except Exception as exc:
        report = {"status": "BLOCKED", "gate_passed": False,
                  "error_type": type(exc).__name__, "pnc_authentication_verified": False}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report["status"] + " | PnC authentication: NOT VERIFIED")
    print("Report:", out)
    raise SystemExit(0 if report["gate_passed"] else 2)

if __name__ == "__main__":
    main()


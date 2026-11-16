#!/usr/bin/env python3
"""Real upstream mock eMSP + real billing, isolated loopback processes.
Posts synthetic CDRs only to the disposable mock started by this script.
Not an EVerest, CSMS, PnC or payment test. No live stack is contacted.
"""
from __future__ import annotations
import argparse, base64, copy, json, os, secrets, shutil, socket, subprocess, sys, tempfile, threading, time, uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from billing.app import make_server
from billing.engine import Engine, sha

def http(url, headers=None, data=None):
    request = Request(url, headers={"Content-Type": "application/json", **(headers or {})},
                      data=None if data is None else json.dumps(data).encode())
    with urlopen(request, timeout=10) as response:
        return response.status, json.load(response)

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "diagnostics/official-mock-billing.json"))
    args = parser.parse_args()
    vendor = ROOT / "vendor/citrineos-core"
    pin = json.loads((ROOT / "UPSTREAM.lock.json").read_text())["citrineos_core"]["commit"]
    head = subprocess.check_output(["git", "-C", str(vendor), "rev-parse", "HEAD"], text=True).strip()
    if head != pin:
        raise SystemExit("Unexpected upstream HEAD; no services started")
    app = vendor / "apps/mock-msp"
    if not (app / "dist/index.js").is_file() or not shutil.which("node"):
        raise SystemExit("Build first: corepack pnpm --filter @citrineos/mock-msp... install --frozen-lockfile; corepack pnpm --filter @citrineos/mock-msp... build (from vendor/citrineos-core)")
    control, inbound, outbound, billing_token = [secrets.token_urlsafe(32) for _ in range(4)]
    port = free_port()
    mock_url = f"http://127.0.0.1:{port}"
    # Explicitly point optional CPO probes at a closed loopback port; never a user's backend.
    closed = free_port()
    process = None
    billing = None
    thread = None
    report = {
        "scope": "OFFICIAL_MOCK_EMSP_TO_BILLING_WITH_SYNTHETIC_OCPI_CDR",
        "upstream_commit": pin, "cases": [], "passed": False,
        "everest_executed": False, "citrineos_csms_executed": False,
        "pnc_verified": False, "payment_executed": False,
    }
    with tempfile.TemporaryDirectory(prefix="coop-mock-wire-") as temp:
        env = {**os.environ,
            "NODE_ENV": "test", "MOCK_MSP_HOST": "127.0.0.1", "MOCK_MSP_PORT": str(port),
            "MOCK_MSP_PUBLIC_BASE_URL": mock_url + "/ocpi",
            "MOCK_MSP_CONTROL_SECRET": control, "MOCK_MSP_CLIENT_TOKEN": inbound,
            "MOCK_MSP_SERVER_TOKEN": outbound, "MOCK_MSP_SCENARIO": "",
            "MOCK_MSP_AUTO_REGISTER": "0", "MOCK_MSP_LOG_LEVEL": "silent",
            "CITRINE_OCPI_BASE_URL": f"http://127.0.0.1:{closed}/ocpi",
            "CITRINE_VERSIONS_URL": f"http://127.0.0.1:{closed}/ocpi/versions/1",
            "CITRINE_HASURA_URL": f"http://127.0.0.1:{closed}/v1/graphql",
        }
        mh = {"x-mock-control-secret": control}
        try:
            with open(Path(temp) / "upstream-process.log", "w") as log:
                process = subprocess.Popen(["node", "dist/index.js"], cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Official mock process exited before becoming healthy")
                    try:
                        _, health = http(mock_url + "/_mock/health", mh)
                        if health.get("status") == "up":
                            break
                    except (OSError, ValueError):
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Official mock health timed out")
                    time.sleep(0.2)
                # Check control API protection; the secret is never put into the report.
                try:
                    http(mock_url + "/_mock/health")
                    raise RuntimeError("Control API unexpectedly accepted missing secret")
                except HTTPError as exc:
                    if exc.code != 401:
                        raise
                policy = json.loads((ROOT / "config/retail_policy.json").read_text())
                engine = Engine(Path(temp) / "billing.sqlite3", policy)
                billing = make_server(engine, billing_token, "127.0.0.1", 0, mock_url, control, str(Path(temp) / "captures"))
                thread = threading.Thread(target=billing.serve_forever, daemon=True)
                thread.start()
                billing_url = "http://127.0.0.1:" + str(billing.server_address[1])
                bh = {"Authorization": "Bearer " + billing_token}
                fixture = json.loads((ROOT / "fixtures/cdr_baseline.json").read_text())
                for label, energy, expected in [("baseline", 10, 3000), ("under_report", 5, 1500), ("over_report", 15, 4500)]:
                    cdr = copy.deepcopy(fixture)
                    suffix = uuid.uuid4().hex[:10]
                    cdr.update(id="SYNTH-" + suffix, session_id="SYNTH-SESSION-" + suffix, total_energy=energy)
                    cdr["charging_periods"][0]["dimensions"][0]["volume"] = energy
                    # Test the real upstream seeded identity, not only the custom fixture identity.
                    cdr["cdr_token"]["contract_id"] = "USTSTC012345678"
                    cdr["total_cost"]["excl_vat"] = energy * 200
                    wire_headers = {
                        "Authorization": "Token " + base64.b64encode(inbound.encode()).decode(),
                        "OCPI-from-country-code": "US", "OCPI-from-party-id": "S44",
                        "OCPI-to-country-code": "US", "OCPI-to-party-id": "TST",
                        "X-Request-ID": str(uuid.uuid4()), "X-Correlation-ID": str(uuid.uuid4()),
                    }
                    status, reply = http(mock_url + "/ocpi/2.2.1/emsp/cdrs", wire_headers, cdr)
                    if not 200 <= status < 300 or reply.get("status_code") != 1000:
                        raise RuntimeError("Official OCPI receiver rejected synthetic CDR")
                    _, sync = http(billing_url + "/api/sync", bh, {})
                    matching = [row.get("invoice", {}) for row in sync["results"] if row.get("invoice", {}).get("cdr_sha256") == sha(cdr)]
                    if len(matching) != 1 or matching[0]["amount_minor"] != expected:
                        raise RuntimeError("Actual HTTP sync did not produce the expected invoice")
                    _, exchanges = http(mock_url + "/_mock/received/cdrs?limit=1000", mh)
                    wire = [ex for ex in exchanges if ex.get("request", {}).get("body", {}).get("id") == cdr["id"]]
                    if len(wire) != 1 or wire[0].get("validation", {}).get("ok") is not True:
                        report["validation_diagnostics"] = [
                            {"validation": ex.get("validation"),
                             "findings": [{k: finding.get(k) for k in ("severity", "kind", "detail")} for finding in ex.get("findings", [])]}
                            for ex in wire]
                        raise RuntimeError("Official OCPI schema/header validation did not pass")
                    report["cases"].append({"case": label, "synthetic_energy_kwh": energy,
                        "invoice_amount_minor": expected, "currency": "KRW",
                        "actual_ocpi_http_status": status, "official_schema_valid": True,
                        "actual_billing_http_sync": True})
                _, repeated = http(billing_url + "/api/sync", bh, {})
                _, invoice_list = http(billing_url + "/api/invoices", bh)
                if len(invoice_list["invoices"]) != 3 or any(row["status"] != "DUPLICATE" for row in repeated["results"]):
                    raise RuntimeError("Repeated sync caused duplicate billing")
                report.update(passed=True, control_secret_required=True, duplicate_sync_no_extra_invoice=True)
        except Exception as exc:
            report["failure_type"] = type(exc).__name__
            # Generic step errors contain no token/body/identifier data.
            report["failure_step"] = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        finally:
            if billing:
                billing.shutdown()
                billing.server_close()
            if thread:
                thread.join(timeout=3)
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)

if __name__ == "__main__":
    main()


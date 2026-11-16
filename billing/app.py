"""Loopback-first research API. No Stripe client, no card collection, no payment calls."""
from __future__ import annotations
import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from billing.engine import Engine, canonical, utc_now

MAX_BODY = 2_000_000


def extract_cdrs(state: object) -> list[dict]:
    """Citrine mock /_mock/state/cdrs returns a map keyed by id.
    Accept the full state's cdrs slice too for exported files; never guess a CDR.
    """
    if not isinstance(state, dict):
        raise ValueError("Expected a CDR object map from /_mock/state/cdrs")
    if "cdrs" in state:
        state = state["cdrs"]
    if not isinstance(state, dict):
        raise ValueError("cdrs must be an object map")
    values = list(state.values())
    if any(not isinstance(x, dict) or "id" not in x for x in values):
        raise ValueError("Unexpected mock state shape; inspect the pinned upstream API")
    return values


def sync_once(engine: Engine, base_url: str, control_secret: str, evidence_dir: str) -> dict:
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("MOCK_MSP_BASE_URL must be a base HTTP URL without credentials/query")
    # URL comes from the operator's environment, never from a supplied CDR.
    url = base_url.rstrip("/") + "/_mock/state/cdrs"
    headers = {"Accept": "application/json"}
    if control_secret:
        headers["x-mock-control-secret"] = control_secret
    with urlopen(Request(url, headers=headers), timeout=10) as response:
        data = response.read(MAX_BODY + 1)
    if len(data) > MAX_BODY:
        raise ValueError("Mock state exceeds capture limit; export smaller batches")
    objects = extract_cdrs(json.loads(data))
    stamp = utc_now()
    # Save only CDR slice; full mock state contains registration credentials.
    out = Path(evidence_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / (stamp.replace(":", "-") + "-cdr-snapshot.json")
    dest.write_text(json.dumps({"observed_at": stamp, "source_url": url, "cdrs": objects}, ensure_ascii=False, indent=2), encoding="utf-8")
    results = [engine.process(cdr, source="citrine-mock-state-snapshot") for cdr in objects]
    return {"observed_at": stamp, "count": len(objects), "results": results, "capture": str(dest),
            "scope": "Read-only snapshot adapter. Capture /_mock/received/cdrs separately for wire/duplicate-delivery evidence.",
            "empty_is_not_success": len(objects) == 0}


def make_server(engine: Engine, token: str, bind: str, port: int, mock_url: str = "", mock_secret: str = "", evidence_dir: str = "evidence") -> ThreadingHTTPServer:
    if len(token) < 24:
        raise ValueError("BILLING_API_TOKEN must contain at least 24 characters")

    class Handler(BaseHTTPRequestHandler):
        server_version = "CoopLabBilling/0.1"

        def log_message(self, fmt: str, *args: object) -> None:
            # Don't log Authorization, token, query string, or CDR contents.
            sys.stderr.write(f"{utc_now()} {self.command} {urlsplit(self.path).path}\n")

        def respond(self, status: int, body: object) -> None:
            raw = canonical(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def authorized(self) -> bool:
            if not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {token}"):
                self.respond(401, {"error": "unauthorized"})
                return False
            return True

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/health":
                self.respond(200, {"status": "up", "payment_enabled": False, "component": "mock-retail-billing"})
                return
            if not self.authorized():
                return
            if path == "/api/invoices":
                self.respond(200, {"invoices": engine.invoices()})
            elif path == "/api/events":
                self.respond(200, {"events": engine.events()})
            else:
                self.respond(404, {"error": "not_found"})

        def do_POST(self) -> None:
            if not self.authorized():
                return
            path = urlsplit(self.path).path
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > MAX_BODY:
                    self.respond(413, {"error": "body_too_large"})
                    return
                data = self.rfile.read(length)
                if path == "/api/sync":
                    if not mock_url:
                        self.respond(409, {"error": "MOCK_MSP_BASE_URL_not_configured"})
                        return
                    result = sync_once(engine, mock_url, mock_secret, evidence_dir)
                    self.respond(200, result)
                elif path == "/api/bill-cdr":
                    # Manual/fixture input is explicitly labelled; this is NOT an OCPI endpoint.
                    result = engine.process(json.loads(data), source="manual-api-input")
                    self.respond(201 if result["status"] == "INVOICED" else 200, result)
                else:
                    self.respond(404, {"error": "not_found"})
            except (ValueError, json.JSONDecodeError) as exc:
                self.respond(400, {"error": "invalid_input", "detail": str(exc)})
            except (HTTPError, URLError, TimeoutError) as exc:
                self.respond(502, {"error": "mock_unavailable", "detail": type(exc).__name__})

    return ThreadingHTTPServer((bind, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default=os.getenv("BILLING_POLICY", "config/retail_policy.json"))
    parser.add_argument("--db", default=os.getenv("BILLING_DB", "data/billing.sqlite3"))
    parser.add_argument("--bind", default=os.getenv("BILLING_BIND", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("BILLING_PORT", "18088")))
    args = parser.parse_args()
    engine = Engine(args.db, json.loads(Path(args.policy).read_text(encoding="utf-8")))
    server = make_server(engine, os.getenv("BILLING_API_TOKEN", ""), args.bind, args.port,
                         os.getenv("MOCK_MSP_BASE_URL", ""), os.getenv("MOCK_MSP_CONTROL_SECRET", ""),
                         os.getenv("BILLING_EVIDENCE_DIR", "evidence"))
    print(f"Mock billing: http://{args.bind}:{args.port}; payment provider DISABLED", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()

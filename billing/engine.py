"""Small, explicit retail-billing policy; not a full OCPI validator or payment service.

Money is calculated with Decimal, rounded once in the currency's minor units.
Accepted CDRs and the tariff snapshot are immutable. Audit events include refusals.
The reference energy is intentionally NOT an input to the billing calculation.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

CURRENCY_DIGITS = {"KRW": 0, "USD": 2, "EUR": 2}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def decimal_value(value: Any, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError(f"{field}: expected a finite number")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid number") from exc
    if not d.is_finite() or abs(d) > Decimal("1000000000"):
        raise ValueError(f"{field}: non-finite/out-of-profile value")
    return d


def text(obj: dict[str, Any], field: str, max_length: int = 128) -> str:
    val = obj.get(field)
    if not isinstance(val, str) or not val.strip() or len(val) > max_length:
        raise ValueError(f"{field}: required nonempty string (max {max_length})")
    return val


def parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field}: missing timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError(f"{field}: timezone is required")
    return dt


def validate_critical_fields(cdr: Any) -> tuple[str, str, Decimal]:
    """Validate only the documented billing subset, NOT full OCPI conformance."""
    if not isinstance(cdr, dict):
        raise ValueError("CDR must be an object")
    country, party, cid = text(cdr, "country_code", 2), text(cdr, "party_id", 3), text(cdr, "id", 39)
    if len(country) != 2 or len(party) != 3 or not country.isalpha() or not party.isalnum():
        raise ValueError("invalid CPO identity")
    # session_id is optional in OCPI but required by this laboratory policy.
    session = text(cdr, "session_id", 36)
    start, end = parse_time(cdr.get("start_date_time"), "start_date_time"), parse_time(cdr.get("end_date_time"), "end_date_time")
    if end <= start:
        raise ValueError("end_date_time must be after start_date_time")
    energy = decimal_value(cdr.get("total_energy"), "total_energy")
    duration = decimal_value(cdr.get("total_time"), "total_time")
    if energy < 0 or duration <= 0:
        raise ValueError("energy must be nonnegative; total_time must be positive")
    currency = text(cdr, "currency", 3)
    if currency not in CURRENCY_DIGITS:
        raise ValueError("unsupported currency (no FX conversion is performed)")
    tok = cdr.get("cdr_token")
    if not isinstance(tok, dict):
        raise ValueError("missing cdr_token")
    for field, n in [("country_code", 2), ("party_id", 3), ("uid", 36), ("type", 16), ("contract_id", 36)]:
        text(tok, field, n)
    cost = cdr.get("total_cost")
    if not isinstance(cost, dict):
        raise ValueError("total_cost must be an OCPI Price object")
    if decimal_value(cost.get("excl_vat"), "total_cost.excl_vat") < 0:
        raise ValueError("negative ordinary CDR cost")
    return f"{country}|{party}|{cid}", f"{country}|{party}|{session}", energy


class Engine:
    def __init__(self, db: str | Path, policy: dict[str, Any]):
        self.db = str(db)
        Path(self.db).parent.mkdir(parents=True, exist_ok=True)
        # Work with an independent copy: changing caller-owned dicts cannot alter a running policy.
        self.policy = json.loads(canonical(policy))
        with self.connect() as con:
            con.executescript("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY, cdr_key TEXT NOT NULL UNIQUE,
                session_key TEXT NOT NULL UNIQUE, cdr_sha256 TEXT NOT NULL,
                payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL, payload TEXT NOT NULL
            );
            """)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db, timeout=20)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA busy_timeout=20000")
        return con

    def _event(self, con: sqlite3.Connection, result: dict[str, Any], source: str) -> dict[str, Any]:
        event = {**result, "source": source, "observed_at": utc_now()}
        con.execute("INSERT INTO events(created_at,payload) VALUES (?,?)", (event["observed_at"], canonical(event)))
        return result

    def process(self, cdr: Any, source: str = "fixture") -> dict[str, Any]:
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            # Credits have special OCPI semantics. Never silently bill them as new sessions.
            if isinstance(cdr, dict) and (cdr.get("credit") is True or cdr.get("credit_reference_id")):
                return self._event(con, {"status": "HELD", "reason": "CREDIT_REQUIRES_MANUAL_REVIEW"}, source)
            try:
                key, session_key, energy = validate_critical_fields(cdr)
                fingerprint = sha(cdr)
            except (ValueError, TypeError, InvalidOperation) as exc:
                return self._event(con, {"status": "REJECTED", "reason": "INVALID_BILLING_FIELDS", "detail": str(exc)}, source)
            existing = con.execute("SELECT * FROM invoices WHERE cdr_key=?", (key,)).fetchone()
            if existing:
                if existing["cdr_sha256"] == fingerprint:
                    return self._event(con, {"status": "DUPLICATE", "invoice": json.loads(existing["payload"])}, source)
                return self._event(con, {"status": "HELD", "reason": "CONFLICTING_CDR", "cdr_key": key}, source)
            if con.execute("SELECT 1 FROM invoices WHERE session_key=?", (session_key,)).fetchone():
                return self._event(con, {"status": "HELD", "reason": "SESSION_ALREADY_INVOICED", "cdr_key": key}, source)
            account = None
            fields = ("country_code", "party_id", "uid", "type", "contract_id")
            for a in self.policy.get("accounts", []):
                if any(all(cdr["cdr_token"].get(k) == identity.get(k) for k in fields) for identity in a.get("identities", [])):
                    account = a
                    break
            if account is None:
                return self._event(con, {"status": "HELD", "reason": "UNKNOWN_CONTRACT", "cdr_key": key}, source)
            currency = cdr["currency"]
            tariff = account.get("tariffs_by_currency", {}).get(currency)
            if not tariff:
                return self._event(con, {"status": "HELD", "reason": "NO_RETAIL_TARIFF_FOR_CURRENCY", "cdr_key": key}, source)
            rate = decimal_value(tariff.get("rate_per_kwh"), "rate_per_kwh")
            if rate < 0:
                raise ValueError("configuration error: negative retail tariff")
            digits = CURRENCY_DIGITS[currency]
            raw = energy * rate
            rounded = raw.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
            inv = {
                "invoice_id": "SIM-" + hashlib.sha256(key.encode()).hexdigest()[:20],
                "status": "SIMULATED_INVOICE_NOT_PAID", "document_kind": "LAB_BILLING_STATEMENT",
                "created_at": utc_now(), "account_id": account["account_id"],
                "cdr_key": key, "session_key": session_key, "cdr_id": cdr["id"],
                "session_id": cdr["session_id"], "energy_kwh": str(energy),
                "currency": currency, "amount_decimal": str(rounded),
                "amount_minor": int(rounded.scaleb(digits)), "minor_unit_digits": digits,
                "unrounded_amount": str(raw), "rounding": "ROUND_HALF_UP_ON_FINAL_TOTAL",
                "tariff_snapshot": tariff, "policy_sha256": sha(self.policy),
                "cpo_total_cost": cdr["total_cost"], "cdr_sha256": fingerprint,
                "cdr_snapshot": cdr, "source": source,
                "payment_attempted": False, "signature_verification": "NOT_IMPLEMENTED",
                "validation_scope": "critical billing fields only; not full OCPI conformance",
                "tax_model": "laboratory flat tariff; no VAT/tax computation",
            }
            con.execute("INSERT INTO invoices VALUES (?,?,?,?,?,?)", (inv["invoice_id"], key, session_key, fingerprint, canonical(inv), inv["created_at"]))
            return self._event(con, {"status": "INVOICED", "invoice": inv}, source)

    def invoices(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT payload FROM invoices ORDER BY created_at,invoice_id")]

    def events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [json.loads(r[0]) for r in con.execute("SELECT payload FROM events ORDER BY event_id DESC LIMIT ?", (min(max(limit, 1), 1000),))]

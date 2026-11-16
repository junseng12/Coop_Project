"""Offline billing smoke test. Fixtures only: not an EVerest/CitrineOS E2E result."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from billing.engine import Engine

ROOT = Path(__file__).resolve().parents[1]

def run_demo() -> dict:
    policy = json.loads((ROOT / "config/retail_policy.json").read_text())
    cdr = json.loads((ROOT / "fixtures/cdr_baseline.json").read_text())
    results = []
    with TemporaryDirectory() as tmp:
        e = Engine(Path(tmp) / "demo.sqlite3", policy)
        for case, energy in [("baseline", 10), ("under_report", 5), ("over_report", 15)]:
            obj = copy.deepcopy(cdr)
            obj["id"] = f"CDR-{case}"
            obj["session_id"] = f"SESSION-{case}"
            obj["total_energy"] = energy
            obj["charging_periods"][0]["dimensions"][0]["volume"] = energy
            obj["total_cost"] = {"excl_vat": energy * 200}
            result = e.process(obj, source="synthetic-cdr-fixture")
            results.append({"case": case, "reference_energy_kwh_for_comparison_only": 10,
                            "reported_energy_kwh": energy, "status": result["status"],
                            "customer_amount_krw": result["invoice"]["amount_minor"],
                            "cpo_total_cost": obj["total_cost"],
                            "invoice_id": result["invoice"]["invoice_id"]})
        assert [x["customer_amount_krw"] for x in results] == [3000, 1500, 4500]
    return {"scope": "BILLING_COMPONENT_TEST_WITH_SYNTHETIC_CDRS", "everest_executed": False,
            "citrineos_executed": False, "ocpi_network_executed": False, "payment_executed": False,
            "cases": results}

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out")
    args = p.parse_args()
    payload = json.dumps(run_demo(), ensure_ascii=False, indent=2)
    print(payload)
    if args.out:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()

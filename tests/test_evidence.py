import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_backend", ROOT / "scripts/verify_backend.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class EvidenceCorrelationTests(unittest.TestCase):
    def setUp(self):
        self.cdr = json.loads((ROOT / "fixtures/cdr_baseline.json").read_text())
        self.exchange = {
            "direction": "inbound", "module": "cdrs",
            "request": {"method": "POST", "body": copy.deepcopy(self.cdr)},
            "response": {"httpStatus": 201, "ocpiStatusCode": 1000},
            "validation": {"ok": True},
            "timing": {"receivedAt": "2026-11-15T01:00:00Z"}}
        self.invoice = {
            "cdr_sha256": probe.sha(self.cdr), "session_id": self.cdr["session_id"],
            "source": "citrine-mock-state-snapshot", "status": "SIMULATED_INVOICE_NOT_PAID"}
        self.transaction = {"transactionId": self.cdr["session_id"], "stationId": "cp001", "isActive": False}
    def evaluate(self, **kwargs):
        values = dict(cdrs=[self.cdr], exchanges=[self.exchange], invoices=[self.invoice],
                      transactions=[self.transaction], station="cp001")
        values.update(kwargs)
        return probe.correlate(**values)[0]
    def test_complete_data_chain_requires_each_independent_source(self):
        self.assertTrue(self.evaluate()["data_chain_observed"])
    def test_empty_recording_is_not_success(self):
        self.assertEqual(probe.correlate([], [], [], [], "cp001"), [])
    def test_stored_schema_invalid_cdr_cannot_pass(self):
        self.exchange["validation"]["ok"] = False
        self.assertFalse(self.evaluate()["data_chain_observed"])
    def test_manual_fixture_invoice_cannot_pass(self):
        self.invoice["source"] = "manual-api-input"
        self.assertFalse(self.evaluate()["data_chain_observed"])
    def test_http_success_without_ocpi_success_cannot_pass(self):
        self.exchange["response"]["ocpiStatusCode"] = 2001
        self.assertFalse(self.evaluate()["data_chain_observed"])
    def test_prior_run_trace_is_excluded(self):
        self.assertFalse(self.evaluate(since="2026-11-15T02:00:00Z")["data_chain_observed"])
    def test_active_transaction_is_not_completed(self):
        self.transaction["isActive"] = True
        self.assertFalse(self.evaluate()["data_chain_observed"])
    def test_changed_wire_energy_is_not_same_cdr(self):
        self.exchange["request"]["body"]["total_energy"] = 999
        self.assertFalse(self.evaluate()["data_chain_observed"])
    def test_different_station_is_not_same_chain(self):
        self.transaction["stationId"] = "other"
        self.assertFalse(self.evaluate()["data_chain_observed"])

if __name__ == "__main__":
    unittest.main()


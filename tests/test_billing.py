from __future__ import annotations
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from billing.engine import Engine
from billing.app import make_server, extract_cdrs
from billing.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]

class BillingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy = json.loads((ROOT / 'config/retail_policy.json').read_text())
        self.cdr = json.loads((ROOT / 'fixtures/cdr_baseline.json').read_text())
        self.db = Path(self.tmp.name) / 'db.sqlite3'
        self.e = Engine(self.db, self.policy)
    def tearDown(self):
        self.tmp.cleanup()
    def result(self, **changes):
        obj=copy.deepcopy(self.cdr); obj.update(changes)
        return self.e.process(obj)
    def test_baseline(self):
        r=self.result(); self.assertEqual(r['status'],'INVOICED'); self.assertEqual(r['invoice']['amount_minor'],3000)
    def test_under(self):
        self.assertEqual(self.result(total_energy=5)['invoice']['amount_minor'],1500)
    def test_over(self):
        self.assertEqual(self.result(total_energy=15)['invoice']['amount_minor'],4500)
    def test_cpo_cost_is_not_retail(self):
        self.assertEqual(self.result(total_cost={'excl_vat':99999})['invoice']['amount_minor'],3000)
    def test_duplicate_no_double_bill(self):
        a=self.result(); b=self.result(); self.assertEqual(b['status'],'DUPLICATE'); self.assertEqual(a['invoice']['invoice_id'],b['invoice']['invoice_id']); self.assertEqual(len(self.e.invoices()),1)
    def test_conflicting_id(self):
        self.result(); self.assertEqual(self.result(total_energy=15)['reason'],'CONFLICTING_CDR'); self.assertEqual(self.e.invoices()[0]['amount_minor'],3000)
    def test_same_session_new_cdr_held(self):
        self.result(); self.assertEqual(self.result(id='NEW-ID')['reason'],'SESSION_ALREADY_INVOICED')
    def test_unknown_identity(self):
        t=copy.deepcopy(self.cdr['cdr_token']); t['uid']='OTHER'
        self.assertEqual(self.result(cdr_token=t)['reason'],'UNKNOWN_CONTRACT')
    def test_contract_mismatch(self):
        t=copy.deepcopy(self.cdr['cdr_token']); t['contract_id']='OTHER'
        self.assertEqual(self.result(cdr_token=t)['reason'],'UNKNOWN_CONTRACT')
    def test_negative_energy(self):
        self.assertEqual(self.result(total_energy=-1)['status'],'REJECTED')
    def test_nonfinite(self):
        for value in ['NaN','Infinity',float('nan')]:
            self.assertEqual(self.result(total_energy=value)['status'],'REJECTED')
    def test_boolean_not_energy(self):
        self.assertEqual(self.result(total_energy=True)['status'],'REJECTED')
    def test_invalid_timestamps(self):
        self.assertEqual(self.result(end_date_time=self.cdr['start_date_time'])['status'],'REJECTED')
    def test_timezone_required(self):
        self.assertEqual(self.result(start_date_time='2026-11-14T00:00:00')['status'],'REJECTED')
    def test_missing_lab_session(self):
        x=copy.deepcopy(self.cdr); del x['session_id']; self.assertEqual(self.e.process(x)['status'],'REJECTED')
    def test_credit_not_charged(self):
        self.assertEqual(self.result(credit=True)['reason'],'CREDIT_REQUIRES_MANUAL_REVIEW'); self.assertEqual(len(self.e.invoices()),0)
    def test_no_implicit_fx(self):
        self.assertEqual(self.result(currency='JPY')['status'],'REJECTED')
    def test_usd_minor_units(self):
        self.assertEqual(self.result(currency='USD')['invoice']['amount_minor'],300)
    def test_round_once_krw(self):
        self.assertEqual(self.result(total_energy='0.005')['invoice']['amount_minor'],2)
    def test_zero_energy(self):
        self.assertEqual(self.result(total_energy=0)['invoice']['amount_minor'],0)
    def test_persistence(self):
        self.result(); again=Engine(self.db,self.policy); self.assertEqual(again.process(self.cdr)['status'],'DUPLICATE')
    def test_tariff_snapshot_immutable(self):
        self.result(); p=copy.deepcopy(self.policy); p['accounts'][0]['tariffs_by_currency']['KRW']['rate_per_kwh']='400'
        changed=Engine(self.db,p); r=changed.process(self.cdr); self.assertEqual(r['invoice']['amount_minor'],3000)
    def test_audit_refusal(self):
        self.result(total_energy=-1); self.assertEqual(self.e.events()[0]['status'],'REJECTED')
    def test_no_payment_claim(self):
        r=self.result()['invoice']; self.assertFalse(r['payment_attempted']); self.assertEqual(r['status'],'SIMULATED_INVOICE_NOT_PAID')
    def test_multiple_cpos_unique_id(self):
        self.result(); r=self.result(party_id='OTH'); self.assertEqual(r['status'],'INVOICED'); self.assertEqual(len(self.e.invoices()),2)
    def test_snapshot_map(self):
        self.assertEqual(extract_cdrs({'CDR':self.cdr}),[self.cdr])
    def test_bad_snapshot_shape(self):
        with self.assertRaises(ValueError): extract_cdrs({'unknown':[]})
    def test_demo_scope(self):
        r=run_demo(); self.assertFalse(r['everest_executed']); self.assertEqual([x['customer_amount_krw'] for x in r['cases']],[3000,1500,4500])

class HttpTests(BillingTests):
    # Only explicitly defined HTTP tests run here, without duplicating inherited cases.
    def setUp(self):
        super().setUp()
        self.token='laboratory-test-secret-at-least-24'
        self.server=make_server(self.e,self.token,'127.0.0.1',0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); super().tearDown()
    def test_http_health(self):
        with urlopen(self.url+'/health') as r: self.assertFalse(json.load(r)['payment_enabled'])
    def test_http_auth(self):
        with self.assertRaises(HTTPError) as ctx: urlopen(self.url+'/api/invoices')
        self.assertEqual(ctx.exception.code,401)
    def test_http_bill(self):
        req=Request(self.url+'/api/bill-cdr',data=json.dumps(self.cdr).encode(),headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
        with urlopen(req) as r: self.assertEqual(json.load(r)['status'],'INVOICED')
    def test_http_sync_not_configured(self):
        req=Request(self.url+'/api/sync',data=b'',headers={'Authorization':'Bearer '+self.token})
        with self.assertRaises(HTTPError) as ctx: urlopen(req)
        self.assertEqual(ctx.exception.code,409)

# Avoid re-running inherited engine tests in the HTTP fixture class.
for _name in list(BillingTests.__dict__):
    if _name.startswith('test_') and _name not in HttpTests.__dict__:
        setattr(HttpTests,_name,None)

if __name__=='__main__': unittest.main()

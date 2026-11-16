import copy,json,tempfile,threading,unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from billing.engine import Engine
from billing.app import sync_once
ROOT=Path(__file__).resolve().parents[1]

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.home=Path(self.tmp.name)
        self.cdr=json.loads((ROOT/'fixtures/cdr_baseline.json').read_text())
        self.policy=json.loads((ROOT/'config/retail_policy.json').read_text())
        self.engine=Engine(self.home/'db.sqlite3',self.policy)
        self.state={'x':self.cdr}; self.headers=[]; owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.headers.append(dict(self.headers)); owner.last_path=self.path
                raw=json.dumps(owner.state).encode(); self.send_response(200); self.end_headers(); self.wfile.write(raw)
            def log_message(self,*args): pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_address[1]}'
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def sync(self):
        return sync_once(self.engine,self.url,'test-control-secret',str(self.home/'capture'))
    def test_read_only_snapshot_bridge(self):
        r=self.sync(); self.assertEqual(r['count'],1); self.assertEqual(r['results'][0]['status'],'INVOICED'); self.assertEqual(self.last_path,'/_mock/state/cdrs')
        self.assertEqual(self.headers[0].get('X-Mock-Control-Secret'),'test-control-secret')
    def test_second_sync_no_second_invoice(self):
        self.sync(); self.assertEqual(self.sync()['results'][0]['status'],'DUPLICATE'); self.assertEqual(len(self.engine.invoices()),1)
    def test_empty_is_not_e2e_success(self):
        self.state={}; r=self.sync(); self.assertTrue(r['empty_is_not_success']); self.assertEqual(len(self.engine.invoices()),0)
    def test_snapshot_conflict_held(self):
        self.sync(); self.state['x']['total_energy']=12
        self.assertEqual(self.sync()['results'][0]['reason'],'CONFLICTING_CDR')
    def test_evidence_has_no_registration_secret(self):
        r=self.sync(); data=Path(r['capture']).read_text(); self.assertNotIn('test-control-secret',data); self.assertNotIn('registration',data)
    def test_bad_shape_fails_closed(self):
        self.state={'unexpected':['not-a-cdr']}
        with self.assertRaises(ValueError): self.sync()

if __name__=='__main__': unittest.main()

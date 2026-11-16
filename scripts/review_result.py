#!/usr/bin/env python3
"""Save a readable report plus independently collected PnC/transaction evidence."""
import argparse
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import html
import json
from pathlib import Path
import subprocess
from uuid import UUID
from verify_backend import env_values, request_json

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('out', type=Path)
p.add_argument('--manager', default='coop-everest-local-manager-1')
p.add_argument('--runtime-config', default='/ext/source/config/config-sil-ocpp201-pnc.yaml')
a = p.parse_args()
out = a.out.resolve()
delivery = json.loads((out / 'delivery.json').read_text())
since = datetime.fromisoformat((out / 'since.txt').read_text().strip()).isoformat()
tids = [str(UUID(x['session_id'])) for x in delivery['correlations'] if x['data_chain_observed']]
if not tids:
    raise SystemExit('No verified delivery correlation')

def docker(*args):
    return subprocess.check_output(['docker', *args], text=True)

def sql(query):
    return json.loads(docker('exec', 'coop-sil-billing-ocpp-db-1', 'psql', '-U', 'citrine', '-d', 'citrine', '-At', '-c', "SELECT coalesce(json_agg(t),'[]'::json) FROM (" + query + ') t'))

v = env_values()
invoices = request_json('http://127.0.0.1:18088/api/invoices', {'Authorization': 'Bearer ' + v['BILLING_API_TOKEN']})['invoices']
runtime = docker('exec', a.manager, 'cat', a.runtime_config)
paths = docker('exec', a.manager, 'find', '/evidence/session-logs', '-name', 'eventlog.csv').splitlines()
results = []
for tid in tids:
    tx = sql('''SELECT "transactionId", "isActive", "totalKwh", "startTime", "endTime" FROM "Transactions" WHERE "transactionId"=''' + "'" + tid + "'")
    events = sql('''SELECT timestamp, "eventType", "seqNo", "idTokenValue", "transactionInfo"->>'transactionId' AS transaction_id FROM "TransactionEvents" WHERE "transactionInfo"->>'transactionId'=''' + "'" + tid + "' ORDER BY timestamp")
    auth = sql('''SELECT timestamp, "correlationId", type, payload FROM "OCPPMessages" WHERE action='Authorize' AND timestamp >= ''' + "'" + since + "' ORDER BY timestamp")
    path = next(x for x in paths if tid in x)
    log = docker('exec', a.manager, 'cat', path)
    (out / (tid + '-eventlog.csv')).write_text(log)
    invoice = next(x for x in invoices if x['cdr_id'] == tid)
    start = datetime.fromisoformat(tx[0]['startTime'])
    requests = [x for x in auth if x['type'] == 2 and x['payload'].get('idToken', {}).get('type') == 'eMAID' and x['payload']['idToken']['idToken'] == 'NL123C10028948M' and x['payload'].get('iso15118CertificateHashData') and 0 <= (start - datetime.fromisoformat(x['timestamp'])).total_seconds() <= 15]
    accepted = any(resp['type'] == 3 and resp['correlationId'] == req['correlationId'] and resp['payload'].get('idTokenInfo', {}).get('status') == 'Accepted' and resp['payload'].get('certificateStatus') == 'Accepted' for req in requests for resp in auth)
    checks = {
        'runtime_strict_certificate_chain': 'verify_contract_cert_chain: true' in runtime,
        'session_payment_details': 'PaymentDetailsReq' in log,
        'session_authorization': 'AuthorizationReq' in log and 'PnC Authorization received' in log,
        'session_finished': 'Transaction Finished' in log,
        'csms_token_and_certificate_accepted': accepted,
        'transaction_completed_with_energy': tx[0]['isActive'] is False and tx[0]['totalKwh'] > 0 and bool(tx[0]['endTime']),
        'started_updated_ended': {'Started', 'Updated', 'Ended'}.issubset({x['eventType'] for x in events}),
        'db_cdr_invoice_energy_equal': Decimal(str(tx[0]['totalKwh'])) == Decimal(str(invoice['cdr_snapshot']['total_energy'])) == Decimal(invoice['energy_kwh']),
        'retail_calculation_correct': (Decimal(invoice['energy_kwh']) * Decimal(invoice['tariff_snapshot']['rate_per_kwh'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) == Decimal(invoice['amount_decimal']),
        'no_payment': invoice['payment_attempted'] is False and invoice['status'] == 'SIMULATED_INVOICE_NOT_PAID',
    }
    results.append({'transaction_id': tid, 'checks': checks, 'passed': all(checks.values()), 'transactions': tx, 'events': events, 'authorize': auth, 'invoice': {k: invoice[k] for k in ['invoice_id', 'cdr_id', 'energy_kwh', 'unrounded_amount', 'amount_decimal', 'currency', 'payment_attempted', 'status']}})
report = {'passed': delivery['gate_passed'] and all(x['passed'] for x in results), 'scope': 'Local runtime replay: PnC evidence, OCPP/OCPI delivery and simulated billing; no physical meter or payment verification.', 'results': results}
(out / 'review-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
body = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>로컬 재실행 결과</title><style>body{font:17px/1.7 sans-serif;max-width:1000px;margin:40px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f9;padding:16px}</style><h1>로컬 구성 재실행 결과: ' + ('통과' if report['passed'] else '확인 필요') + '</h1><p>/home/hyebin 없이 로컬 Compose와 이 PC에 보존한 runtime 이미지로 실행했습니다. 실제 결제와 물리 계량 검증은 포함하지 않습니다.</p><p>각 검사항목 true는 이번 실행에서 수집한 증거로 통과했다는 뜻입니다. Authorize 요청/응답은 거래 시작 전 15초 이내의 eMAID 요청과 동일 correlationId 응답으로 대조했습니다.</p><pre>' + html.escape(json.dumps(report, ensure_ascii=False, indent=2)) + '</pre><p><a href="delivery.json">전달·청구 상관관계 JSON</a> · <a href="manager.log">manager 로그</a></p></html>'
(out / 'result.html').write_text(body)
print('Review:', out / 'result.html')
if not report['passed']:
    raise SystemExit(1)

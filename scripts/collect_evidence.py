#!/usr/bin/env python3
"""Read-only exports from mock eMSP and billing. Review output before sharing."""
import argparse,json,os,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]

def env_values():
    result={}
    f=ROOT/'.env'
    if f.exists():
        for line in f.read_text().splitlines():
            if line and not line.startswith('#') and '=' in line:
                k,v=line.split('=',1); result[k]=v
    result.update({k:v for k,v in os.environ.items() if k in ('BILLING_API_TOKEN','MOCK_MSP_CONTROL_SECRET')})
    return result

def scrub(obj):
    if isinstance(obj,dict):
        return {k:('[REDACTED]' if k.lower() in ('authorization','x-mock-control-secret','token','access_token','api_key','password','secret') else scrub(v)) for k,v in obj.items()}
    if isinstance(obj,list): return [scrub(v) for v in obj]
    if isinstance(obj,str):
        return re.sub(r'(?i)(Bearer|Token)\s+[A-Za-z0-9+/_=.-]{12,}',r'\1 [REDACTED]',obj)
    return obj

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mock-url',default='http://127.0.0.1:18083')
    p.add_argument('--billing-url',default='http://127.0.0.1:18088')
    p.add_argument('--include-wire',action='store_true',help='Include CDR exchanges; may still contain identifiers. Review before sharing.')
    args=p.parse_args(); vals=env_values()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=ROOT/'evidence'/stamp; out.mkdir(parents=True,exist_ok=False)
    endpoints=[('mock-health',args.mock_url+'/_mock/health','mock'),('cdrs',args.mock_url+'/_mock/state/cdrs','mock'),('findings',args.mock_url+'/_mock/findings','mock'),('invoices',args.billing_url+'/api/invoices','billing'),('billing-events',args.billing_url+'/api/events','billing')]
    if args.include_wire:
        endpoints.append(('cdr-wire',args.mock_url+'/_mock/received/cdrs?limit=1000','mock'))
    failures=[]
    for name,url,kind in endpoints:
        headers={'x-mock-control-secret':vals.get('MOCK_MSP_CONTROL_SECRET','')} if kind=='mock' else {'Authorization':'Bearer '+vals.get('BILLING_API_TOKEN','')}
        try:
            with urlopen(Request(url,headers=headers),timeout=10) as resp: data=resp.read(10_000_001)
            if len(data)>10_000_000: raise ValueError('export size cap exceeded')
            (out/f'{name}.json').write_text(json.dumps(scrub(json.loads(data)),ensure_ascii=False,indent=2),encoding='utf-8')
        except Exception as exc:
            failures.append({'endpoint':name,'error_type':type(exc).__name__})
    (out/'manifest.json').write_text(json.dumps({'scope':'selected mock/Billing endpoint exports; not proof of PnC, metering truth, or payment','failures':failures,'wire_limit':1000,'truncated_trace_possible':True},indent=2),encoding='utf-8')
    print(f'Exports: {out}. Review identifiers before sharing; never commit raw evidence.')
    if failures: raise SystemExit(1)

if __name__=='__main__': main()

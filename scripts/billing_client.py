#!/usr/bin/env python3
"""Local client that reads the gitignored .env without echoing its credentials."""
import argparse, json, os
from pathlib import Path
from urllib.request import Request,urlopen
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('action',choices=['health','invoices','events','sync']); p.add_argument('--url',default='http://127.0.0.1:18088'); args=p.parse_args()
vals={}
if (root/'.env').exists():
    vals=dict(line.strip().split('=',1) for line in (root/'.env').read_text().splitlines() if line and not line.startswith('#') and '=' in line)
token=os.getenv('BILLING_API_TOKEN',vals.get('BILLING_API_TOKEN',''))
path='/health' if args.action=='health' else '/api/'+args.action
req=Request(args.url.rstrip('/')+path, headers={'Authorization':'Bearer '+token},data=b'' if args.action=='sync' else None)
with urlopen(req,timeout=30) as r:
    print(json.dumps(json.load(r),ensure_ascii=False,indent=2))

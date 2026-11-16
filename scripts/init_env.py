#!/usr/bin/env python3
"""Write lab-local secrets once; never overwrite an existing .env."""
import os, secrets
from pathlib import Path
root=Path(__file__).resolve().parents[1]
target=root/'.env'
if target.exists():
    print('Existing .env preserved.')
else:
    data='BILLING_API_TOKEN='+secrets.token_urlsafe(32)+'\nMOCK_MSP_CONTROL_SECRET='+secrets.token_urlsafe(32)+'\n'
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(data)
    print('Created .env (local-only secrets). Do not commit this file.')

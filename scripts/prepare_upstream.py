#!/usr/bin/env python3
"""Clone only into this kit's vendor/ and apply one verified laboratory DNS patch.
Does not touch the user's EVerest tree or existing Docker containers/volumes.
"""
from __future__ import annotations
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LOCK=json.loads((ROOT/'UPSTREAM.lock.json').read_text())['citrineos_core']
TARGET=ROOT/'vendor/citrineos-core'
SEED='apps/ocpi-server/db/seeders/20250806120002-default-tenant-partner.ts'
OLD='http://host.docker.internal:8083'
NEW='http://mock-msp:8083'

def cmd(*args):
    return subprocess.check_output(args,text=True).strip()

def main():
    if not TARGET.exists():
        TARGET.parent.mkdir(parents=True,exist_ok=True)
        subprocess.run(['git','clone','--filter=blob:none','--no-checkout',LOCK['url'],str(TARGET)],check=True)
        subprocess.run(['git','-C',str(TARGET),'checkout','--detach',LOCK['commit']],check=True)
    if cmd('git','-C',str(TARGET),'rev-parse','HEAD')!=LOCK['commit']:
        raise SystemExit('Existing vendor checkout has a different HEAD. Preserved; no reset/checkout performed.')
    raw=subprocess.check_output(['git','-C',str(TARGET),'show',f'{LOCK["commit"]}:{SEED}']).decode()
    if OLD not in raw:
        raise SystemExit('Expected upstream seed text is absent. Stop rather than guessing.')
    patched=raw.replace(OLD,NEW)
    path=TARGET/SEED
    current=path.read_text(encoding='utf-8')
    if current not in (raw,patched):
        raise SystemExit('Seed has user modifications. Preserved; manual review required.')
    # Reject other modifications to tracked source files. Untracked local data is left alone.
    changed=cmd('git','-C',str(TARGET),'diff','--name-only').splitlines()
    staged=cmd('git','-C',str(TARGET),'diff','--cached','--name-only').splitlines()
    if any(name!=SEED for name in changed) or staged:
        raise SystemExit('Vendor source has other modifications. Preserved; review manually.')
    path.write_text(patched,encoding='utf-8')
    out=ROOT/'diagnostics'; out.mkdir(exist_ok=True)
    (out/'vendor-patch.json').write_text(json.dumps({'base_commit':LOCK['commit'],'path':SEED,'old':OLD,'new':NEW,'replacements':raw.count(OLD),'patched_sha256':hashlib.sha256(patched.encode()).hexdigest()},indent=2))
    print('Prepared source-pinned candidate. Only OCPI seeded mock endpoint DNS was patched.')
    print('Next: bash scripts/stack.sh config (validation only), then review docs/SETUP.md.')

if __name__=='__main__': main()

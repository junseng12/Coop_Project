#!/usr/bin/env python3
"""Scan EVERY saved image layer for embedded PEM keys and SQLite runtime DBs."""
import argparse,json,re,subprocess,tarfile,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('image');p.add_argument('--out',required=True);a=p.parse_args()
private=re.compile(rb'(?m)^-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?$')
findings=[];layers=0;files=0
with tempfile.TemporaryDirectory(prefix='coop-image-audit-') as temp:
 path=Path(temp)/'image.tar'
 subprocess.run(['docker','image','save','-o',str(path),a.image],check=True)
 with tarfile.open(path) as saved:
  manifests=json.load(saved.extractfile('manifest.json'))
  for entry in manifests:
   for name in entry['Layers']:
    layers+=1
    with tarfile.open(fileobj=saved.extractfile(name),mode='r|*') as layer:
     for f in layer:
      if not f.isfile():continue
      files+=1
      stream=layer.extractfile(f)
      head=stream.read(min(f.size,8_000_000))
      reasons=[]
      if private.search(head): reasons.append('PEM private key')
      if head.startswith(b'SQLite format 3\x00'):reasons.append('SQLite database')
      if Path(f.name).suffix.lower() in {'.key','.p12','.pfx','.jks'}:reasons.append('key/keystore extension')
      if reasons:findings.append({'layer':name,'path':f.name,'reasons':reasons})
report={'image':a.image,'layers_scanned':layers,'files_scanned':files,'findings':findings,'passed':not findings,'limits':'PEM and SQLite signatures and key extensions; not a universal secret detector. No findings are not proof that arbitrary encoded secrets cannot exist.'}
Path(a.out).parent.mkdir(parents=True,exist_ok=True)
Path(a.out).write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)

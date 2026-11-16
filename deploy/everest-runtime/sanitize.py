"""Construct a clean final rootfs from an immutable official binary input."""
import hashlib,json,re,shutil,subprocess
from pathlib import Path
root=Path('/clean'); root.mkdir()
for name in ['bin','sbin','lib','lib64','usr','etc']:
 p=Path('/'+name); dest=root/name
 if p.is_symlink(): dest.symlink_to(p.readlink())
 elif p.exists(): shutil.copytree(p,dest,symlinks=True)
shutil.copytree('/ext/dist',root/'ext/dist',symlinks=True)
# Keep PKI recipes, never their pre-generated outputs.
pki=root/'ext/dist/libexec/everest/3rd_party/josev/iso15118/shared/pki'
shutil.copytree(pki,root/'opt/coop/pki-template',ignore=shutil.ignore_patterns('iso15118_2','iso15118_20','__pycache__'))
shutil.rmtree(pki)
pki.symlink_to('/state/pki')
shutil.rmtree(root/'ext/dist/etc/everest/certs')
(root/'ext/dist/etc/everest/certs').symlink_to('/state/certs')
# Preserve config templates without SQLite runtime state.
for p in list(root.rglob('*')):
 if p.is_symlink() or not p.is_file(): continue
 if p.suffix.lower() in {'.db','.sqlite','.sqlite3','.key','.p12','.pfx','.jks'} or p.name.endswith(('.db-wal','.db-shm')):
  p.unlink()
# Drop host identity, authentication and caches from the upstream OS input.
for rel in ['etc/ssh','etc/ssl/private','etc/machine-id','etc/shadow','etc/gshadow','etc/subuid','etc/subgid','etc/hostname','etc/hosts','etc/resolv.conf']:
 p=root/rel
 if p.is_dir(): shutil.rmtree(p)
 elif p.exists() or p.is_symlink(): p.unlink()
# Package test material can contain example PEM keys. It is not needed at runtime.
private=re.compile(rb'(?m)^-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?$')
removed=[]
for p in root.rglob('*'):
 if p.is_symlink() or not p.is_file(): continue
 if p.stat().st_size > 8_000_000: continue
 if private.search(p.read_bytes()):
  removed.append(str(p.relative_to(root))); p.unlink()
# Runtime paths remain empty in the image. OCPP DB paths are explicitly /state.
for rel in ['state','evidence','tmp','run','dev','proc','sys','var/tmp','var/log','root','ext/source/config']:
 (root/rel).mkdir(parents=True,exist_ok=True)
(root/'tmp').chmod(0o1777); (root/'var/tmp').chmod(0o1777)
(root/'ext/source/config/certs').symlink_to('/state/certs')
(root/'usr/share/coop').mkdir(parents=True,exist_ok=True)
rev='c86cd9c0ada60b5797f574fd484eae4d8330017d'
files={str(p.relative_to('/ext/dist')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/ext/dist/libexec/everest/modules').glob('*/manifest.yaml')}
provenance={'upstream_image':'ghcr.io/everest/everest-demo/manager@sha256:9165d0937323ae61ee2e496f68f3c4a465ed9099740e489df1f0161265492756','everest_core_commit':rev,'everest_demo_commit':'686e370d6ed6460211b06e34a4cdf9438a22e81e','build_method':'binary-derived clean multi-stage image; not a fresh C++ compilation','removed_pem_key_files':removed,'source_module_manifest_sha256':files}
(root/'usr/share/coop/PROVENANCE.json').write_text(json.dumps(provenance,indent=2))
print('Clean runtime rootfs ready',flush=True)

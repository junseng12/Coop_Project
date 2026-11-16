"""Idempotently create experiment-specific PKI and mutable OCPP settings."""
import json,os,shutil,subprocess
from pathlib import Path
state=Path('/state'); state.mkdir(exist_ok=True)
(state/'certs').mkdir(exist_ok=True)
for name in ['ocpp','ocpp/core','ocpp/logs','ocsp']:(state/name).mkdir(parents=True,exist_ok=True)
# OCPP's component JSON is a seed; writable DB and queues are in the volume.
component=state/'ocpp/component_config'
if not component.exists():
 shutil.copytree('/ext/dist/share/everest/modules/OCPP201/component_config',component)
 for name in ['EVSE_2.json','Connector_2_1.json']:
  (component/'custom'/name).unlink(missing_ok=True)
 p=component/'standardized/InternalCtrlr.json'
 s=p.read_text().replace('ws://localhost:9000',os.environ.get('CSMS_URL','ws://citrine:8081/cp001'))
 p.write_text(s)
# Work only in the mounted state volume; no cached private keys in the image.
if not (state/'pki-ready').exists():
 pki=state/'pki'
 if pki.exists(): shutil.rmtree(pki)
 shutil.copytree('/opt/coop/pki-template',pki)
 p=pki/'configs/contractLeafCert.cnf'
 import re
 p.write_text(re.sub(r'^commonName.*','commonName = NL123C10028948M',p.read_text(),flags=re.M))
 p.write_text(re.sub(r'^authorityInfoAccess.*','authorityInfoAccess = OCSP;URI:http://manager:8888/',p.read_text(),flags=re.M))
 for name in ['moRootCACert.cnf','moSubCA1Cert.cnf','moSubCA2Cert.cnf']:
  p=pki/'configs'/name
  p.write_text(re.sub(r'^authorityInfoAccess.*\n?','',p.read_text(),flags=re.M))
 # Private passphrases are generated at runtime too.
 import secrets
 subprocess.run(['sh','./create_certs.sh','-v','iso-2','-p',secrets.token_hex(16),'-i','/ext/source'],cwd=pki,check=True)
 source=Path('/ext/source/config/certs')
 # /ext/source/config/certs points to /state/certs; generator populates it.
 certs=state/'certs'
 shutil.copy2(certs/'ca/v2g/V2G_ROOT_CA.pem',certs/'ca/csms/CSMS_ROOT_CA.pem')
 leaf=certs/'client/mo/MO_LEAF.pem'
 expiry=subprocess.check_output(['openssl','x509','-in',str(leaf),'-noout','-enddate'],text=True).strip().split('=',1)[1]
 expiry=subprocess.check_output(['date','-u','-d',expiry,'+%y%m%d%H%M%SZ'],text=True).strip()
 serial=subprocess.check_output(['openssl','x509','-in',str(leaf),'-noout','-serial'],text=True).strip().split('=',1)[1]
 (state/'ocsp/index.txt').write_text(f'V\t{expiry}\t\t{serial}\tunknown\t/CN=NL123C10028948M\n')
 for p in state.rglob('*'):
  if p.is_file() and (p.suffix in {'.key','.p12'} or 'PASSWORD' in p.name):p.chmod(0o600)
 (state/'pki-ready').write_text('Test PKI generated locally; never publish this volume.\n')
# Module manifests support absolute DB/config paths; never write into the image.
import yaml
cfg=yaml.safe_load(Path('/config/everest.yaml').read_text())
modules=cfg['active_modules']
modules['evse_security'].setdefault('config_module',{})['private_key_password']=(state/'certs/client/cso/SECC_LEAF_PASSWORD.txt').read_text().strip()
modules['error_history']['config_implementation']['error_history']['database_path']='/state/error_history.db'
ocpp=next(x for x in modules.values() if x['module']=='OCPP201')
ocpp.setdefault('config_module',{}).update({'CoreDatabasePath':'/state/ocpp/core','MessageLogPath':'/state/ocpp/logs','DeviceModelDatabasePath':'/state/ocpp/device_model_storage.db','EverestDeviceModelDatabasePath':'/state/ocpp/everest_device_model_storage.db','DeviceModelConfigPath':'/state/ocpp/component_config'})
(state/'everest.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
print('Local state initialized. PKI preserved on subsequent starts.',flush=True)

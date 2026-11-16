#!/usr/bin/env python3
"""Read-only project/Docker audit. Writes only the requested JSON report.
Does not read .env contents, private keys, certificate bodies, or container Env.
"""
from __future__ import annotations
import argparse, json, os, platform, re, shutil, sqlite3, subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit


def run(cmd, timeout=15):
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
        return {'exit_code':p.returncode,'stdout':p.stdout[:120000],'stderr':p.stderr[:2000]}
    except (OSError,subprocess.TimeoutExpired) as e:
        return {'error':str(e)}


def scrub_url(value):
    return re.sub(r'(https?://)[^/@\s]+@',r'\1[REDACTED]@',value)


def audit(root, vscode_state=None):
    root=Path(root).expanduser().resolve()
    report={'created_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'root':str(root),
            'privacy':'No .env contents, private keys, Docker Env or file bodies collected. Paths and repo names may be personal; review before sharing.',
            'tools':{},'repositories':[],'configuration_paths':[],'docker':{},'vscode_relevant_recent':[]}
    for label,cmd in [('git',['git','--version']),('python',['python3','--version']),('node',['node','--version']),('pnpm',['pnpm','--version']),('docker',['docker','--version']),('compose',['docker','compose','version'])]:
        report['tools'][label]=run(cmd)
    skip={'.git','node_modules','.venv','venv','build','dist','.cache','data','evidence','vendor'}
    visited=0
    for here,dirs,files in os.walk(root):
        visited+=1
        depth=len(Path(here).relative_to(root).parts)
        if '.git' in dirs or '.git' in files:
            meta={'path':here,'head':run(['git','-C',here,'rev-parse','HEAD']),
                  'describe':run(['git','-C',here,'describe','--tags','--always','--dirty']),
                  'status':run(['git','-C',here,'status','--porcelain']),
                  'remote':run(['git','-C',here,'remote','-v'])}
            if 'stdout' in meta['remote']: meta['remote']['stdout']=scrub_url(meta['remote']['stdout'])
            report['repositories'].append(meta)
        for name in files:
            if (name.startswith(('docker-compose','compose','config-sil')) and name.endswith(('.yml','.yaml'))) or name.endswith('.code-workspace') or name in ('EV 충전 과금 실증 구조.md','EV 충전 과금 실증 구조.html'):
                report['configuration_paths'].append(str(Path(here)/name))
        dirs[:]=[] if depth>=4 or visited>=400 else [d for d in dirs if d not in skip and not d.startswith('.')]
        if visited>=400: break
    report['docker']['ps']=run(['docker','ps','-a','--format','{{json .}}'])
    listing=run(['docker','ps','-aq'])
    ids=listing.get('stdout','').split()
    report['docker']['relevant_containers']=[]
    for cid in ids[:60]:
        # Explicit field whitelist: never dump full inspect JSON/Env.
        data=run(['docker','inspect','--format','{{json .Name}}|{{json .Config.Image}}|{{json .Image}}|{{json .Mounts}}|{{json (index .Config.Labels "com.docker.compose.project.working_dir")}}|{{json (index .Config.Labels "com.docker.compose.project.config_files")}}',cid])
        raw=data.get('stdout','')
        if any(x in raw.lower() for x in ('everest','citrine','maeve','coop')):
            entry={'id':cid,'selected_fields':raw}
            if 'manager' in raw.lower() and any(x in raw.lower() for x in ('everest','ev-pnc')):
                script='/ext/build/run-scripts/run-sil-ocpp201-pnc.sh'
                entry['pnc_run_script_probe']=run(['docker','exec',cid,'test','-f',script])
                # Read the OCPP device model only through sqlite's read-only mode.
                # Discard raw JSON and expose only whitelisted connection metadata.
                probe=run(['docker','exec',cid,'sqlite3','-readonly',
                    '/ext/dist/share/everest/modules/OCPP201/device_model_storage.db',
                    "SELECT VALUE FROM VARIABLE_ATTRIBUTE WHERE VARIABLE_ID = (SELECT ID FROM VARIABLE WHERE NAME='NetworkConnectionProfiles');"])
                profiles=[]
                try:
                    value=json.loads(probe.get('stdout',''))
                    for item in value if isinstance(value,list) else []:
                        c=item.get('connectionData',{})
                        u=urlsplit(c.get('ocppCsmsUrl',''))
                        profiles.append({'ocpp_version':c.get('ocppVersion'),
                            'security_profile':c.get('securityProfile'),
                            'csms_scheme':u.scheme,'csms_host':u.hostname,
                            'csms_port':u.port,'station_path':u.path})
                    entry['ocpp_profiles']=profiles
                except (ValueError,TypeError,AttributeError):
                    entry['ocpp_profile_status']='UNAVAILABLE_OR_DIFFERENT_LAYOUT'
            report['docker']['relevant_containers'].append(entry)
    report['root_exists']=root.is_dir()
    report['disk_free_bytes']=shutil.disk_usage(root if root.is_dir() else Path.home()).free
    if vscode_state:
        try:
            state=Path(vscode_state).expanduser().resolve()
            con=sqlite3.connect(state.as_uri()+'?mode=ro',uri=True)
            rows=con.execute("SELECT value FROM ItemTable WHERE key='history.recentlyOpenedPathsList'").fetchall(); con.close()
            for row in rows:
                obj=json.loads(row[0])
                entries=obj.get('entries',[]) if isinstance(obj,dict) else []
                for entry in entries:
                    if any(x in json.dumps(entry).lower() for x in ('everest','citrine','coop','ev-pnc')):
                        report['vscode_relevant_recent'].append(entry)
        except (OSError,sqlite3.Error,ValueError) as e:
            report['vscode_read_error']=str(e)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',default=os.getcwd(),help='Existing EVerest workspace root, not necessarily this kit')
    p.add_argument('--out',default='local-audit.json')
    p.add_argument('--vscode-state',help='Optional explicit path to VS Code User/globalStorage/state.vscdb (read-only)')
    a=p.parse_args(); target=Path(a.out).expanduser(); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(audit(a.root,a.vscode_state),ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Wrote read-only audit: {target.resolve()}')

if __name__=='__main__': main()

#!/usr/bin/env python3
"""Refuse lab startup while Windows commit headroom is low."""
import json
import subprocess
import sys

PS = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
cmd = ('$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; '
       '@{used=[double]$m.CommittedBytes; limit=[double]$m.CommitLimit} | ConvertTo-Json -Compress')
try:
    r = subprocess.run([PS, '-NoProfile', '-Command', cmd], capture_output=True, text=True, timeout=20, check=True)
    d = json.loads(r.stdout.lstrip('\ufeff'))
    headroom = (d['limit'] - d['used']) / 1024**3
    percent = 100 * d['used'] / d['limit']
except Exception as exc:
    sys.exit('Cannot verify Windows commit headroom: ' + type(exc).__name__)
print(f'Windows commit: {percent:.1f}%, headroom: {headroom:.2f} GiB')
if percent >= 85 or headroom < 6:
    sys.exit('BLOCKED: enable Windows automatic pagefile management, restart Windows, and retry. Need >=6 GiB commit headroom and <85% use.')

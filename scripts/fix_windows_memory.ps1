param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$system = Get-CimInstance Win32_ComputerSystem
$pagefiles = @(Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize)
$memory = Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory
$state = [ordered]@{
    CheckedAt = (Get-Date).ToString('o')
    AutomaticManagedPagefile = $system.AutomaticManagedPagefile
    Pagefiles = $pagefiles
    CommitGB = [math]::Round($memory.CommittedBytes / 1GB, 2)
    LimitGB = [math]::Round($memory.CommitLimit / 1GB, 2)
    PercentCommitted = $memory.PercentCommittedBytesInUse
}
$state | ConvertTo-Json -Depth 4
if (-not $Apply) { Write-Host 'Read-only. To enable automatic pagefile management: run this script with -Apply in Administrator PowerShell.'; exit 0 }
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw 'Administrator PowerShell is required. No settings changed.' }
$backup = Join-Path $PSScriptRoot ('../diagnostics/windows-memory-before-' + (Get-Date -Format yyyyMMddTHHmmss) + '.json')
New-Item -ItemType Directory -Force (Split-Path $backup) | Out-Null
$state | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $backup
Set-CimInstance -InputObject $system -Property @{AutomaticManagedPagefile = $true}
if (-not (Get-CimInstance Win32_ComputerSystem).AutomaticManagedPagefile) { throw 'Setting did not apply.' }
Write-Host "Automatic pagefile management enabled. Backup: $backup"
Write-Host 'Save your work and restart Windows manually. This script does not restart Windows.'

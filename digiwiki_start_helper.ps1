# Startet genau einen digiwiki_helpers.ps1-Hintergrundprozess (Watchdog).
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$helper = Join-Path $root 'digiwiki_helpers.ps1'
$pidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'

if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -match '^\d+$') {
        $proc = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -match '^powershell') {
            Write-Host "HELPER=LAUFEND PID=$oldPid"
            exit 0
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Start-Process powershell -ArgumentList @(
    '-NoProfile', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass',
    '-File', $helper, '-WatchPid', '0'
) -WindowStyle Hidden | Out-Null
Write-Host 'HELPER=GESTARTET'

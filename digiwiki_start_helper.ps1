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

for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    $alive = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
        Where-Object { [string]$_.CommandLine -match 'digiwiki_helpers\.ps1' } |
        Select-Object -First 1
    if ($alive) {
        [int]$alive.ProcessId | Out-File -FilePath $pidFile -Encoding ascii -Force
        Write-Host "HELPER=GESTARTET PID=$($alive.ProcessId)"
        exit 0
    }
}
Write-Host 'HELPER=FEHLER'
exit 1

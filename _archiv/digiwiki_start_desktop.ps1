param(
    [string]$ProjectRoot = $PSScriptRoot
)

Set-Location -LiteralPath $ProjectRoot

$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$pythonw = Join-Path $ProjectRoot '.venv\Scripts\pythonw.exe'
$ui = Join-Path $ProjectRoot '14_wiki_master_ui.py'
$pidFile = Join-Path $env:TEMP 'digiwiki_desktop.pid'
$logFile = Join-Path $env:TEMP 'digiwiki_desktop.log'

function Stop-DigiWikiDesktop {
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -match '14_wiki_master_ui\.py' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

function Test-DesktopAlive([int]$ProcessId) {
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Start-DesktopProcess([string]$ExePath) {
    return Start-Process -FilePath $ExePath -ArgumentList "`"$ui`"" -WorkingDirectory $ProjectRoot -PassThru
}

if (-not (Test-Path $python)) {
    Write-Host '[FEHLER] .venv\Scripts\python.exe nicht gefunden.'
    exit 1
}

if (-not (Test-Path $ui)) {
    Write-Host '[FEHLER] 14_wiki_master_ui.py nicht gefunden.'
    exit 1
}

Stop-DigiWikiDesktop

& $python -c 'import markdown, PyQt5' 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host '[INFO] Installiere markdown + PyQt5 ...'
    & $python -m pip install markdown PyQt5 -q
}

$started = $null
if (Test-Path $pythonw) {
    $started = Start-DesktopProcess $pythonw
    Start-Sleep -Seconds 4
    if (Test-DesktopAlive $started.Id) {
        $started.Id | Out-File -FilePath $pidFile -Encoding ascii -Force
        Write-Host "[OK] Desktop-UI gestartet (PID $($started.Id))"
        exit 0
    }
    "$(Get-Date -Format o) pythonw beendet sich sofort (PID $($started.Id))" | Out-File -FilePath $logFile -Append -Encoding utf8
}

$started = Start-DesktopProcess $python
Start-Sleep -Seconds 4
if (Test-DesktopAlive $started.Id) {
    $started.Id | Out-File -FilePath $pidFile -Encoding ascii -Force
    Write-Host "[OK] Desktop-UI gestartet via python.exe (PID $($started.Id))"
    exit 0
}

try {
    $probe = Start-Process -FilePath $python -ArgumentList "`"$ui`"" -WorkingDirectory $ProjectRoot -PassThru -NoNewWindow -Wait -RedirectStandardError $logFile
    "$(Get-Date -Format o) Desktop-Start fehlgeschlagen, ExitCode=$($probe.ExitCode)" | Out-File -FilePath $logFile -Append -Encoding utf8
} catch {
    "$(Get-Date -Format o) Desktop-Start Exception: $_" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Write-Host "[FEHLER] Desktop-UI konnte nicht gestartet werden."
Write-Host "         Log: $logFile"
exit 1

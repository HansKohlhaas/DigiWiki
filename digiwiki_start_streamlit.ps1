# Startet Streamlit genau einmal im Hintergrund (kein zweites CMD-Fenster).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root '.venv\Scripts\python.exe'
$app = Join-Path $root '15_wiki_web_ui.py'
$pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'

if (-not (Test-Path $python)) {
    Write-Host 'ERROR=PYTHON_MISSING'
    exit 1
}

if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host 'ERROR=PORT_BELEGT'
    exit 2
}

if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -match '^\d+$') {
        $old = Get-Process -Id ([int]$oldPid) -ErrorAction SilentlyContinue
        if ($old -and $old.ProcessName -match '^python') {
            Write-Host 'ERROR=BEREITS_LAUFEND'
            exit 2
        }
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$args = @(
    '-m', 'pip', 'install', '-q', 'docx2txt'
)
& $python @args | Out-Null

$streamlitArgs = @(
    '-m', 'streamlit', 'run', $app,
    '--server.address', '0.0.0.0',
    '--server.headless', 'true',
    '--server.enableCORS', 'true',
    '--server.enableXsrfProtection', 'false',
    '--server.enableWebsocketCompression', 'false',
    '--server.websocketPingInterval', '30',
    '--server.disconnectedSessionTTL', '3600'
)

$proc = Start-Process -FilePath $python `
    -ArgumentList $streamlitArgs `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru

. (Join-Path $root 'digiwiki_erreichbarkeit.ps1')
Start-Sleep -Seconds 3
$portPid = Sync-DigiWikiStreamlitPidFile -PidFile $pidFile
if ($portPid -le 0) {
    $proc.Id | Out-File -FilePath $pidFile -Encoding ascii -Force
    Write-Host "STARTED=$($proc.Id)"
} else {
    Write-Host "STARTED=$portPid"
}
exit 0

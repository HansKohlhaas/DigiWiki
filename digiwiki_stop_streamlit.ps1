# Streamlit auf Port 8501 beenden (auch wenn WMI keine Kommandozeile liefert).
$ErrorActionPreference = 'SilentlyContinue'

function Stop-PidForce {
    param([int]$ProcessId)
    if ($ProcessId -le 4) { return $false }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 250
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /F /T /PID $ProcessId 2>$null | Out-Null
        Start-Sleep -Milliseconds 250
    }
    return -not (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

$script:zugriffVerweigert = $false
1..10 | ForEach-Object {
    $listeners = @(Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
    if (-not $listeners) { return }
    foreach ($conn in $listeners) {
        $procId = [int]$conn.OwningProcess
        if ($procId -gt 4) {
            if (-not (Stop-PidForce $procId)) {
                $script:zugriffVerweigert = $true
            }
        }
    }
    Start-Sleep -Milliseconds 400
}

$pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'
if (Test-Path $pidFile) {
    $spid = (Get-Content $pidFile -Raw).Trim()
    if ($spid -match '^\d+$') {
        Stop-PidForce ([int]$spid)
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

$frei = -not (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
if ($frei) {
    Write-Host 'STREAMLIT_STOP=OK'
    exit 0
}
$conn = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Write-Host "STREAMLIT_STOP=FEHLER PID=$($conn.OwningProcess)"
    if ($script:zugriffVerweigert) {
        Write-Host 'STREAMLIT_STOP=ZUGRIFF_VERWEIGERT'
        Write-Host 'Hinweis: Port 8501 gehoert einem Prozess mit hoeheren Rechten (oft Admin).'
        Write-Host '         digiwiki_stop_streamlit_admin.bat per Rechtsklick als Administrator.'
    }
    exit 2
}
Write-Host 'STREAMLIT_STOP=OK'
exit 0

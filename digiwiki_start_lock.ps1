param(
    [ValidateSet('Acquire', 'Release')]
    [string]$Action = 'Acquire'
)

$ErrorActionPreference = 'SilentlyContinue'
$lockPath = Join-Path $env:TEMP 'digiwiki_starting.lock'

function Test-StreamlitPort {
    return [bool](Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
}

if ($Action -eq 'Release') {
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    Write-Host 'LOCK=RELEASED'
    exit 0
}

if (Test-StreamlitPort) {
    Write-Host 'LOCK=RUNNING'
    exit 2
}

if (Test-Path -LiteralPath $lockPath) {
    $age = (Get-Date) - (Get-Item -LiteralPath $lockPath).LastWriteTime
    if ($age.TotalSeconds -lt 90) {
        Write-Host 'LOCK=BUSY'
        exit 2
    }
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType File -Path $lockPath -Force | Out-Null
Write-Host 'LOCK=OK'
exit 0

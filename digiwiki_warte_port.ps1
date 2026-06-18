param([int]$Sekunden = 45)

$ErrorActionPreference = 'SilentlyContinue'
for ($i = 0; $i -lt $Sekunden; $i++) {
    if (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue) {
        Write-Host 'READY=1'
        exit 0
    }
    Start-Sleep -Seconds 1
}
Write-Host 'READY=0'
exit 1

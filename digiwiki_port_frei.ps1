$ErrorActionPreference = 'SilentlyContinue'
$conn = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
    $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
    Write-Host "PORT8501=BELEGT PID=$($conn.OwningProcess) NAME=$name"
    exit 1
}
Write-Host 'PORT8501=FREI'
exit 0

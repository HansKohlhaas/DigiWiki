param(
    [Parameter(Mandatory = $true)]
    [string]$StartBatPath,
    [string]$WindowTitle = ""
)

$candidates = Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" -ErrorAction SilentlyContinue
if (-not $candidates) {
    exit 0
}

$match = $candidates | Where-Object {
    $cmd = $_.CommandLine
    if ($cmd -and ($cmd -like "*$StartBatPath*")) { return $true }
    if ($WindowTitle -and $_.MainWindowTitle -like "*$WindowTitle*") { return $true }
    return $false
} | Sort-Object CreationDate -Descending | Select-Object -First 1

if ($match) {
    Write-Output $match.ProcessId
}

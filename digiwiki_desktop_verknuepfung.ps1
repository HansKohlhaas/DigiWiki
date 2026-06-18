# Erstellt oder aktualisiert die Desktop-Verknuepfung zu start.bat
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startBat = Join-Path $root 'start.bat'
$desktop = [Environment]::GetFolderPath('Desktop')
$linkPath = Join-Path $desktop 'DigiWiki starten.lnk'

if (-not (Test-Path $startBat)) {
    Write-Error "start.bat nicht gefunden: $startBat"
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = $startBat
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 1   # Normal
$shortcut.Description = 'DigiWiki starten (Streamlit, Tailscale, Browser)'

$pythonExe = Join-Path $root '.venv\Scripts\python.exe'
if (Test-Path $pythonExe) {
    $shortcut.IconLocation = "$pythonExe,0"
}

$shortcut.Save()

Write-Host "VERKNUEPFUNG=$linkPath"
exit 0

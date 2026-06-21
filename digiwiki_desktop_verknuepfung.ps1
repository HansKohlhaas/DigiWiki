# Erstellt oder aktualisiert die Desktop-Verknuepfung zu start.bat
$ErrorActionPreference = 'Stop'

function Get-EchterDesktopPfad {
    # Registry = tatsaechlicher Desktop (auch bei OneDrive-Umleitung)
    try {
        $reg = Get-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders' -Name Desktop -ErrorAction Stop
        $pfad = [Environment]::ExpandEnvironmentVariables([string]$reg.Desktop)
        if ($pfad -and (Test-Path -LiteralPath $pfad)) { return $pfad }
    } catch {}
    return [Environment]::GetFolderPath('Desktop')
}

function New-DigiWikiVerknuepfung {
    param([string]$DesktopPfad, [string]$StartBat, [string]$Root)
    if (-not (Test-Path -LiteralPath $DesktopPfad)) {
        New-Item -ItemType Directory -Path $DesktopPfad -Force | Out-Null
    }
    $linkPath = Join-Path $DesktopPfad 'DigiWiki starten.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($linkPath)
    $shortcut.TargetPath = $StartBat
    $shortcut.WorkingDirectory = $Root
    $shortcut.WindowStyle = 1
    $shortcut.Description = 'DigiWiki starten (Streamlit, Tailscale, Browser)'
    # Sichtbares Icon: Windows-Shell (nicht unsichtbares python.exe-Icon)
    $shortcut.IconLocation = "$env:SystemRoot\System32\imageres.dll,109"
    $shortcut.Save()
    return $linkPath
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$startBat = Join-Path $root 'start.bat'

if (-not (Test-Path -LiteralPath $startBat)) {
    Write-Error "start.bat nicht gefunden: $startBat"
    exit 1
}

$desktop = Get-EchterDesktopPfad
$linkPath = New-DigiWikiVerknuepfung -DesktopPfad $desktop -StartBat $startBat -Root $root

# Explorer-Desktop aktualisieren (manchmal erscheint .lnk erst nach F5)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class DesktopRefresh {
    [DllImport("shell32.dll")]
    public static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);
    public static void Refresh() { SHChangeNotify(0x8000000, 0x1000, IntPtr.Zero, IntPtr.Zero); }
}
"@ -ErrorAction SilentlyContinue
[DesktopRefresh]::Refresh() | Out-Null

Write-Host "VERKNUEPFUNG=$linkPath"
Write-Host "DESKTOP=$desktop"
if (-not (Test-Path -LiteralPath $linkPath)) {
    Write-Error "Verknuepfung wurde nicht geschrieben: $linkPath"
    exit 1
}
exit 0

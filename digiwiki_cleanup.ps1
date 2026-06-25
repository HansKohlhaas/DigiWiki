$ErrorActionPreference = 'SilentlyContinue'

$stopped = [System.Collections.Generic.HashSet[int]]::new()

function Stop-DigiWikiPid {
    param([int]$ProcessId)
    if ($ProcessId -le 4) { return }
    if (-not $stopped.Add($ProcessId)) { return }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 200
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        & taskkill.exe /F /T /PID $ProcessId 2>$null | Out-Null
    }
}

function Stop-Tree {
    param([int]$RootPid)
    if ($RootPid -le 4) { return }
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" |
        ForEach-Object { Stop-Tree $_.ProcessId }
    Stop-DigiWikiPid $RootPid
}

$patterns = @(
    'digiwiki_helpers\.ps1',
    'digiwiki_run_streamlit\.bat',
    'digiwiki_tailscale_fix\.ps1',
    '15_wiki_web_ui\.py',
    '14_wiki_master_ui',
    'streamlit run'
)

# Eigene Aufrufkette nicht beenden (start.bat / cleanup gerade aktiv)
$ownPid = $PID
$ownTree = [System.Collections.Generic.HashSet[int]]::new()
function Collect-Tree {
    param([int]$RootPid)
    if ($RootPid -le 4 -or -not $ownTree.Add($RootPid)) { return }
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" |
        ForEach-Object { Collect-Tree $_.ProcessId }
}
Collect-Tree $ownPid

# 0) Watchdog zuerst stoppen (startet sonst Streamlit waehrend des Cleanups neu)
$helperPidFile = Join-Path $env:TEMP 'digiwiki_helper.pid'
if (Test-Path $helperPidFile) {
    $hpid = (Get-Content $helperPidFile -Raw).Trim()
    if ($hpid -match '^\d+$') {
        Stop-Tree ([int]$hpid)
    }
}
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { [string]$_.CommandLine -match 'digiwiki_helpers\.ps1' } |
    ForEach-Object { Stop-Tree $_.ProcessId }

# 0b) Port 8501 sofort freimachen (WMI liefert oft keine Kommandozeile mehr)
$stopScript = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'digiwiki_stop_streamlit.ps1'
if (Test-Path $stopScript) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript | Out-Null
}

# 1) Prozesse anhand der Kommandozeile (zuverlaessiger als Fenstertitel)
Get-CimInstance Win32_Process |
    Where-Object { $_.Name -match '^(python|pythonw|cmd|powershell|pwsh)\.exe$' } |
    ForEach-Object {
        $cmd = [string]$_.CommandLine
        if (-not $cmd) { return }
        foreach ($pattern in $patterns) {
            if ($cmd -match $pattern) {
                if (-not $ownTree.Contains($_.ProcessId)) {
                    Stop-Tree $_.ProcessId
                }
                break
            }
        }
    }

$pidFile = Join-Path $env:TEMP 'digiwiki_streamlit.pid'
if (Test-Path $pidFile) {
    $spid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($spid -match '^\d+$') {
        Stop-Tree ([int]$spid)
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

# 2) CMD-Fenster mit DigiWiki-Titel (Fallback)
Get-Process -Name cmd -ErrorAction SilentlyContinue |
    ForEach-Object {
        $title = [string]$_.MainWindowTitle
        if ($title -match 'DigiWiki') {
            Stop-Tree $_.Id
        }
    }

# 3) Alles, was noch auf Port 8501 lauscht
1..8 | ForEach-Object {
    Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Stop-Tree $_.OwningProcess
            Stop-DigiWikiPid $_.OwningProcess
        }
    if (-not (Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)) {
        return
    }
    Start-Sleep -Milliseconds 600
}

Remove-Item -LiteralPath (Join-Path $env:TEMP 'digiwiki_helper.pid') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $env:TEMP 'digiwiki_streamlit.lock') -Force -ErrorAction SilentlyContinue

Write-Host "STOPPED=$($stopped.Count)"

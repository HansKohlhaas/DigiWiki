param(
    [Parameter(Mandatory = $true)]
    [string]$BatPath,
    [Parameter(Mandatory = $true)]
    [string]$Root
)

$cmdPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
if (-not $cmdPid) { exit 1 }

$grandParentPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$cmdPid").ParentProcessId
if (-not $grandParentPid) { exit 1 }

$grandParentName = (Get-Process -Id $grandParentPid -ErrorAction SilentlyContinue).ProcessName
if ($grandParentName -notmatch '^(powershell|pwsh)$') { exit 1 }

# $Root wird beim Aufruf wegen des abschliessenden '\' von PowerShell verstuemmelt
# (das '\"' wird zu einem woertlichen "), was 'cd /d "$Root"' mit
# 'Die Syntax fuer den Dateinamen ... ist falsch' scheitern laesst.
# Daher das Arbeitsverzeichnis aus dem sauberen $BatPath ableiten.
$workDir = Split-Path -Parent $BatPath

Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/c', "set DIGIWIKI_DETACHED=1& cd /d `"$workDir`"& call `"$BatPath`"" `
    -WindowStyle Normal
exit 0

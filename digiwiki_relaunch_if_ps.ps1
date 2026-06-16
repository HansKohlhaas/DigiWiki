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

Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', "set DIGIWIKI_DETACHED=1& cd /d `"$Root`"& call `"$BatPath`"" `
    -WindowStyle Normal
exit 0

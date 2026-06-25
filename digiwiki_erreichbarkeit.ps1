# Gemeinsame Erreichbarkeits-Checks fuer Keepalive, Watchdog und Diagnose.
$ErrorActionPreference = 'SilentlyContinue'

function Get-DigiWikiStreamlitPortPid {
    $conn = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($conn) { return [int]$conn.OwningProcess }
    return 0
}

function Sync-DigiWikiStreamlitPidFile {
    param([string]$PidFile)
    $portPid = Get-DigiWikiStreamlitPortPid
    if ($portPid -le 0) { return 0 }
    $portPid | Out-File -FilePath $PidFile -Encoding ascii -Force
    return $portPid
}

function Test-DigiWikiStreamlitLocal {
    try {
        $code = (& curl.exe -sS -o NUL -w '%{http_code}' --max-time 8 'http://127.0.0.1:8501/_stcore/health' 2>$null)
        return ($code -eq '200')
    } catch {
        return $false
    }
}

function Get-DigiWikiTailscaleDns {
    try {
        $status = (tailscale status --json 2>$null | ConvertFrom-Json)
        if (-not ($status -and $status.Self.Online)) { return $null }
        $dns = ($status.Self.DNSName -replace '\.$', '')
        if ($dns) { return $dns }
    } catch {}
    return $null
}

function Test-DigiWikiServeWebSocket {
    param([string]$DnsName)
    if (-not $DnsName) { return $false }
    try {
        $out = & curl.exe --max-time 12 -sS -D - -o NUL `
            -H 'Connection: Upgrade' -H 'Upgrade: websocket' `
            -H 'Sec-WebSocket-Version: 13' -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' `
            "https://$DnsName/_stcore/stream" 2>&1
        return ($out -match '101 Switching Protocols')
    } catch {
        return $false
    }
}

function Test-DigiWikiServeHttp {
    param([string]$DnsName)
    if (-not $DnsName) { return $false }
    try {
        $code = (& curl.exe -sS -o NUL -w '%{http_code}' --max-time 12 "https://$DnsName/_stcore/health" 2>$null)
        return ($code -eq '200')
    } catch {
        return $false
    }
}

function Get-DigiWikiErreichbarkeit {
    $dns = Get-DigiWikiTailscaleDns
    $portPid = Get-DigiWikiStreamlitPortPid
    $local = Test-DigiWikiStreamlitLocal
    $remoteHealth = if ($dns) { Test-DigiWikiServeHttp -DnsName $dns } else { $false }
    $remoteWs = if ($dns) { Test-DigiWikiServeWebSocket -DnsName $dns } else { $false }
    [pscustomobject]@{
        Zeit            = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        PortPid         = $portPid
        LokalHealth     = $local
        TailscaleDns    = $dns
        RemoteHealth    = $remoteHealth
        RemoteWebSocket = $remoteWs
        ExternOk        = ($remoteHealth -and $remoteWs)
        GesamtOk        = ($local -and $remoteHealth -and $remoteWs)
    }
}

function Write-DigiWikiErreichbarkeitStatus {
    param(
        [Parameter(Mandatory = $true)]
        $Status,
        [string]$Root
    )
    if (-not $Root) {
        $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $jsonPath = Join-Path $Root 'digiwiki_erreichbarkeit.json'
    $Status | ConvertTo-Json | Set-Content -Path $jsonPath -Encoding UTF8
}

function Get-DigiWikiStreamlitProzesse {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            [string]$_.CommandLine -match 'streamlit\s+run' -and
            [string]$_.CommandLine -match '15_wiki_web_ui'
        }
}

function Test-DigiWikiProcessInTree {
    param(
        [int]$AncestorPid,
        [int]$DescendantPid
    )
    if ($AncestorPid -le 4 -or $DescendantPid -le 4) { return $false }
    $cur = $DescendantPid
    while ($cur -gt 4) {
        if ($cur -eq $AncestorPid) { return $true }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$cur" -ErrorAction SilentlyContinue
        if (-not $proc) { break }
        $cur = [int]$proc.ParentProcessId
    }
    return $false
}

function Get-DigiWikiStreamlitRootPids {
  # Windows-venv: Launcher + Kind-Prozess = eine Instanz, nicht zwei.
    $alle = @(Get-DigiWikiStreamlitProzesse)
    if ($alle.Count -eq 0) { return @() }
    $ids = @($alle | ForEach-Object { [int]$_.ProcessId })
    $roots = New-Object System.Collections.Generic.List[int]
    foreach ($p in $alle) {
        $ppid = [int]$p.ParentProcessId
        if ($ids -contains $ppid) { continue }
        $roots.Add([int]$p.ProcessId) | Out-Null
    }
    return @($roots)
}

function Stop-DigiWikiProcessTree {
    param([int]$RootPid)
    if ($RootPid -le 4) { return }
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$RootPid" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-DigiWikiProcessTree $_.ProcessId }
    Stop-Process -Id $RootPid -Force -ErrorAction SilentlyContinue
}

function Stop-DoppelteStreamlitInstanzen {
    $roots = @(Get-DigiWikiStreamlitRootPids)
    if ($roots.Count -le 1) { return 0 }

    $portPid = Get-DigiWikiStreamlitPortPid
    $keepRoot = 0
    foreach ($root in $roots) {
        if ($portPid -gt 0 -and ($root -eq $portPid -or (Test-DigiWikiProcessInTree $root $portPid))) {
            $keepRoot = $root
            break
        }
    }
    if ($keepRoot -eq 0) { $keepRoot = $roots[0] }

    $gestoppt = 0
    foreach ($root in $roots) {
        if ($root -eq $keepRoot) { continue }
        Stop-DigiWikiProcessTree $root
        $gestoppt++
    }
    return $gestoppt
}

function Repair-DigiWikiTailscaleServe {
    param([string]$DnsName)
    if (-not $DnsName) { return }
    tailscale serve reset 2>$null | Out-Null
    tailscale serve --bg 8501 2>$null | Out-Null
    Start-Sleep -Seconds 2
}

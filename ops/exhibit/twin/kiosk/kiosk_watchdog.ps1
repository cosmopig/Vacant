# Vacant exhibit kiosk watchdog (runs on the TV machine, Windows, every 2 minutes).
#
# Deployed to C:\Users\w401\vacant_kiosk\ by install_watchdog.ps1. ASCII only on purpose
# (Windows PowerShell 5.1 reads BOM-less files with the ANSI code page).
#
# What it guarantees (and what it does not):
#   * The TV page (title "sc=... mode=... hb=N", see world3/index.html) must exist in a Chrome
#     window.  If there is none for ~1 check, Chrome is (re)launched fullscreen on the TV URL.
#   * The page writes a heartbeat into its own title (hb changes every 5 s).  If the title is
#     byte-identical on two checks >= 100 s apart, the renderer is frozen => Chrome is killed
#     and relaunched.  A hung window (IsHungAppWindow) is treated the same way.
#   * A launched Chrome that never shows a TV title within 3 minutes is killed and relaunched.
#   * It does NOT fix a dead VM / dead server: if the exhibit server is unreachable it only
#     logs (reloading a page cannot bring a server back; the page has its own reload logic).
#   * Relaunch is rate limited (>= 90 s apart) so a persistently broken setup does not spin.
#
# Chrome is started with a dedicated profile (--user-data-dir=<dir>\profile) so that killing
# it never touches other Chrome windows of the person using this machine.

$ErrorActionPreference = 'Continue'
$Dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log    = Join-Path $Dir 'watchdog.log'
$State  = Join-Path $Dir 'state.json'
$Chrome = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$Profile = Join-Path $Dir 'profile'
$UrlFile = Join-Path $Dir 'url.txt'
$Url = 'http://192.168.76.135:8420/world3/index.html?live=http://192.168.76.135:8899/live/events.jsonl&poll=2000&twin=http://192.168.76.135:8901/visitors.json'
if (Test-Path $UrlFile) { $u = (Get-Content $UrlFile -Raw).Trim(); if ($u) { $Url = $u } }
$StateUrl = ($Url -replace '^(https?://[^/]+)/.*$', '$1') -replace ':8420$', ':8899'
$StateUrl = $StateUrl + '/state'

function Log($m) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    try {
        if ((Test-Path $Log) -and ((Get-Item $Log).Length -gt 1MB)) { Move-Item $Log "$Log.1" -Force }
        Add-Content -Path $Log -Value $line -Encoding UTF8
    } catch {}
}

Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class Win {
    public delegate bool EnumProc(IntPtr h, IntPtr l);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc p, IntPtr l);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] static extern int GetWindowTextLength(IntPtr h);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool IsHungAppWindow(IntPtr h);
    public static List<string[]> Chrome() {
        var r = new List<string[]>();
        EnumWindows((h, l) => {
            var c = new StringBuilder(256); GetClassName(h, c, 256);
            if (c.ToString() != "Chrome_WidgetWin_1" || !IsWindowVisible(h)) return true;
            int n = GetWindowTextLength(h); var t = new StringBuilder(n + 2); GetWindowText(h, t, n + 2);
            uint pid; GetWindowThreadProcessId(h, out pid);
            r.Add(new string[] { pid.ToString(), t.ToString(), IsHungAppWindow(h) ? "1" : "0" });
            return true;
        }, IntPtr.Zero);
        return r;
    }
}
"@

function Load-State {
    try { if (Test-Path $State) { return (Get-Content $State -Raw | ConvertFrom-Json) } } catch {}
    return [pscustomobject]@{ title = ''; since = 0; launched = 0; lastAction = 0; bad = 0 }
}
function Save-State($s) { try { $s | ConvertTo-Json | Set-Content -Path $State -Encoding UTF8 } catch {} }
function Now-S { [int][double]::Parse((Get-Date -UFormat %s)) }

function Kill-ChromeProfile {
    # Only the kiosk profile's processes (and, for a window we did not launch, its owner pid).
    param($ownerPid)
    $killed = 0
    Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object {
        $_.CommandLine -and $_.CommandLine -like "*$Profile*"
    } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $killed++ }
    if ($killed -eq 0 -and $ownerPid) {
        & taskkill.exe /PID $ownerPid /T /F 2>&1 | Out-Null; $killed = 1
    }
    return $killed
}

function Launch-Chrome {
    New-Item -ItemType Directory -Force -Path $Profile | Out-Null
    $cargs = @("--user-data-dir=`"$Profile`"", '--new-window', '--start-fullscreen', '--no-first-run',
              '--noerrdialogs', '--disable-infobars', '--disable-session-crashed-bubble',
              '--autoplay-policy=no-user-gesture-required', "`"$Url`"")
    Start-Process -FilePath $Chrome -ArgumentList $cargs | Out-Null
}

$now = Now-S
$st = Load-State
foreach ($k in 'since','launched','lastAction','bad') { if ($null -eq $st.$k) { $st | Add-Member -NotePropertyName $k -NotePropertyValue 0 -Force } }

$tv = @(); try { $tv = @([Win]::Chrome() | Where-Object { $_[1] -match 'hb=\d+' -or $_[1] -match 'sc=\w+ mode=' -or $_[1] -match 'Vacant World 3' }) } catch { Log "enum failed: $_" }

# Server reachability is information only.
try { Invoke-WebRequest -Uri $StateUrl -UseBasicParsing -TimeoutSec 4 | Out-Null } catch { Log "note: exhibit /state unreachable ($StateUrl): $($_.Exception.Message)" }

$action = $null
if ($tv.Count -eq 0) {
    $age = $now - [int]$st.launched
    if ($st.launched -gt 0 -and $age -lt 180 -and ($now - [int]$st.lastAction) -lt 90) {
        # just launched, page still loading
    } elseif (($now - [int]$st.lastAction) -ge 90) {
        $action = 'no TV window'
    }
} else {
    $w = $tv[0]; $title = $w[1]; $hung = ($w[2] -eq '1')
    # Frozen-page detection needs the heartbeat (hb=N) the new page version writes into its title;
    # an older page without it can legitimately keep an identical title for minutes, so only the
    # hung-window check applies to it.
    if ($title -eq $st.title) {
        if (($title -match 'hb=\d+') -and (($now - [int]$st.since) -ge 100)) { $action = 'frozen (title unchanged ' + ($now - [int]$st.since) + 's)' }
    } else { $st.title = $title; $st.since = $now }
    if ($hung) { $st.bad = [int]$st.bad + 1; if ($st.bad -ge 2) { $action = 'window hung' } } else { $st.bad = 0 }
    if ($action) { $ownerPid = [int]$w[0] }
}
if (-not $action -and $tv.Count -eq 0 -and $st.launched -gt 0 -and ($now - [int]$st.launched) -ge 180 -and ($now - [int]$st.lastAction) -ge 90) {
    $action = 'launched but no TV title after 3 min'
}

if ($action -and (Test-Path (Join-Path $Dir 'dryrun.txt'))) {
    Log "DRYRUN would act: $action (tv windows seen: $($tv.Count))"; $action = $null
}
if ($action) {
    Log "ACTION: $action -> restart Chrome"
    $n = Kill-ChromeProfile $ownerPid
    Start-Sleep -Seconds 2
    Launch-Chrome
    $st.launched = $now; $st.lastAction = $now; $st.title = ''; $st.since = $now; $st.bad = 0
    Log "relaunched (killed $n process(es))"
}
Log ("check: tv windows=" + $tv.Count + $(if ($tv.Count) { " title=" + $tv[0][1] } else { "" }))
Save-State $st

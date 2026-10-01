# Installs the kiosk watchdog on the TV machine.  Run once (as the logged-in user, no admin needed):
#   powershell -ExecutionPolicy Bypass -File install_watchdog.ps1
# Creates ONE scheduled task "VacantKioskWatchdog": at logon + every 2 minutes, interactive session,
# hidden (launched through wscript so no console window flashes over the fullscreen TV).
# Remove with:  schtasks /delete /tn VacantKioskWatchdog /f
$ErrorActionPreference = 'Stop'
$Dir = 'C:\Users\w401\vacant_kiosk'
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($src -ne $Dir) { Copy-Item (Join-Path $src 'kiosk_watchdog.ps1') $Dir -Force }
$vbs = Join-Path $Dir 'run_hidden.vbs'
$ps  = Join-Path $Dir 'kiosk_watchdog.ps1'
Set-Content -Path $vbs -Encoding ASCII -Value ('CreateObject("Wscript.Shell").Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""{0}""", 0, True' -f $ps)
$act  = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('"{0}"' -f $vbs)
$t1   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$t2   = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
$set  = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$prin = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'VacantKioskWatchdog' -Action $act -Trigger @($t1, $t2) -Settings $set -Principal $prin -Force | Out-Null
Get-ScheduledTask -TaskName 'VacantKioskWatchdog' | Select-Object TaskName, State | Format-List

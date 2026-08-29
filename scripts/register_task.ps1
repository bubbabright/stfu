# scripts/register_task.ps1
# Registers one of STFU's Scheduled Tasks - the single mechanism for all
# autostart on pluto (no NSSM, no ad-hoc Startup-folder .bat).
#
# Usage: register_task.ps1 -Module web|overlay|night-light-helper
#
# - web: Flask + audio control. At-startup, SYSTEM - must work headless,
#   before anyone logs in (pluto has AutoAdminLogon disabled).
# - overlay / night-light-helper: need the interactive desktop session
#   (tkinter, HKCU, WM_SETTINGCHANGE are all session-scoped) - at-logon,
#   the interactive user, same constraint stfu/night_light_helper.py and
#   stfu/theme.py document.
#
# Explicit WorkingDirectory and Principal every time - the two things the
# old ad-hoc overlay Scheduled Task got wrong (blank WorkingDirectory
# silently ran the wrong Python; an implicit principal can silently run as
# whoever happened to register the task instead of the intended account).

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("web", "overlay", "night-light-helper")]
    [string]$Module
)

$ErrorActionPreference = "Stop"

$installDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $installDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Error "venv not found at $pythonExe - run setup.bat first."
    exit 1
}

switch ($Module) {
    "web" {
        $taskName = "STFU_Web"
        $taskArgs = "-m stfu --no-overlay"
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        $description = "STFU web module: Flask + audio control. At-startup/SYSTEM - must work before anyone logs in."
    }
    "overlay" {
        $taskName = "STFU_Overlay"
        $taskArgs = "-m stfu --overlay-only"
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
        $description = "STFU overlay module: tkinter on-screen HUD. Needs the interactive desktop session."
    }
    "night-light-helper" {
        $taskName = "STFU_NightLightHelper"
        $taskArgs = "-m stfu --night-light-helper"
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
        $description = "STFU theme module: Windows Dark Mode control. HKCU/WM_SETTINGCHANGE are session-scoped - needs the interactive desktop session, cannot run under SYSTEM/at-startup."
    }
}

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $taskArgs -WorkingDirectory $installDir

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -ExecutionTimeLimit 0 `
    -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Principal $principal -Settings $settings `
    -Description $description `
    | Out-Null

Write-Host "Registered '$taskName' ($Module module)."
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 1
schtasks /query /tn $taskName /v /fo list | Select-String "Status|Run As User|Logon Mode|Last Run Result"

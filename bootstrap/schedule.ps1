# saipen scheduled inject manager -- Windows Task Scheduler wrapper.
# install (default) -- create/update the 'saipen-inject' task: git pull the
#                      clone + re-inject every agent config, every 15 minutes.
# remove            -- delete the task.
# status            -- task state, last result, next run, log tail.
# run-now           -- trigger the task once immediately.
# The task runs as the current user, only while logged on, no password stored.

param([string]$Command = "install")

$ErrorActionPreference = "Stop"

$TaskName = "saipen-inject"
$Runner = Join-Path $PSScriptRoot "schedule-run.ps1"
$LogFile = Join-Path $env:LOCALAPPDATA "saipen\inject.log"

switch ($Command) {
  "install" {
    if (-not (Test-Path $Runner)) {
      Write-Host "FATAL: $Runner missing" -ForegroundColor Red; exit 1
    }
    if (-not (Test-Path (Join-Path $PSScriptRoot "inject.ps1"))) {
      Write-Host "FATAL: inject.ps1 missing next to $PSScriptRoot" -ForegroundColor Red; exit 1
    }
    # schtasks /SC MINUTE /MO N is the battle-tested way to repeat every N
    # minutes INDEFINITELY. New-ScheduledTaskTrigger -RepetitionDuration
    # cannot say "forever": [TimeSpan]::MaxValue serializes past the Task
    # Scheduler range check (HRESULT 0x80041318) and any finite value stops
    # repeating. Default principal = current logged-on user, interactive.
    $tr = "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$Runner`""
    schtasks /Create /TN $TaskName /TR $tr /SC MINUTE /MO 15 /F 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: schtasks /Create failed" -ForegroundColor Red; exit 1 }
    # Tighten the defaults: kill a hung run at 10 minutes (a git credential
    # wait or a dead network must never occupy a 72-hour default), never stack
    # overlapping runs, and fire a missed run at the next logon.
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
      -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
      -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
    Set-ScheduledTask -TaskName $TaskName -Settings $settings | Out-Null
    Write-Host "Installed: $TaskName -- every 15 min, log -> $LogFile" -ForegroundColor Green
  }
  "remove" {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
      schtasks /Delete /TN $TaskName /F 2>&1 | ForEach-Object { Write-Host $_ }
      Write-Host "Removed: $TaskName" -ForegroundColor Yellow
    } else {
      Write-Host "Not present: $TaskName" -ForegroundColor DarkGray
    }
  }
  "status" {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) {
      Write-Host "Not installed: $TaskName -- run: powershell -ExecutionPolicy Bypass -File $($MyInvocation.MyCommand.Path) install" -ForegroundColor DarkGray
      exit 0
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host ("State            : {0}" -f $t.State)
    Write-Host ("Last run result  : {0}" -f $info.LastTaskResult)
    Write-Host ("Last run time    : {0}" -f $info.LastRunTime)
    Write-Host ("Next run time    : {0}" -f $info.NextRunTime)
    if (Test-Path $LogFile) {
      Write-Host ("Log ({0}), tail:" -f $LogFile)
      Get-Content -LiteralPath $LogFile -Tail 12
    }
  }
  "run-now" {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) {
      Write-Host "Not installed: $TaskName -- run install first" -ForegroundColor Red; exit 1
    }
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Triggered: $TaskName (log -> $LogFile)" -ForegroundColor Green
  }
  default {
    Write-Host "usage: schedule.ps1 [install|remove|status|run-now] (default: install)" -ForegroundColor Yellow
  }
}

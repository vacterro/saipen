# saipen scheduled injector -- the headless body of the 'saipen-inject' task.
# Steps: (1) git pull the clone, best-effort -- a dirty tree or offline machine
# must never block the inject, and a credential prompt must never hang a
# headless task, so git fails fast instead of asking. (2) re-inject every
# agent config from the current tree. Appends one timestamped line per event
# to %LOCALAPPDATA%\saipen\inject.log and mirrors the injector's exit code.

param([string]$CloneRoot = (Split-Path $PSScriptRoot -Parent))

$ErrorActionPreference = "Continue"

$injector = Join-Path $PSScriptRoot "inject.ps1"
if (-not (Test-Path $injector)) {
  Write-Host "FATAL: injector not found: $injector"
  exit 1
}

$logDir = Join-Path $env:LOCALAPPDATA "saipen"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
$log = Join-Path $logDir "inject.log"

function Write-Log([string]$msg) {
  $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

Write-Log "=== saipen scheduled inject ==="

# 1) Pull, best-effort.
$env:GIT_TERMINAL_PROMPT = "0"
$git = Get-Command git -ErrorAction SilentlyContinue
if ($git) {
  & $git.Source -C $CloneRoot pull --ff-only 2>&1 | ForEach-Object { Write-Log ("pull: " + $_) }
  if ($LASTEXITCODE -eq 0) { Write-Log "pull: ok" }
  else { Write-Log "pull: failed (rc $LASTEXITCODE), injecting current tree" }
} else {
  Write-Log "pull: git not found, injecting current tree"
}

# 2) Inject. Write-Host output only leaves a process, not the pipeline (it
#    writes to stream 6), so run the injector as a child and merge every
#    stream into a temp file; only the exit code is authoritative afterwards.
$raw = Join-Path $logDir "inject-raw.log"
& powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $injector *> $raw
$rc = $LASTEXITCODE
if (Test-Path $raw) {
  Get-Content -LiteralPath $raw | ForEach-Object { Write-Log ("inject: " + $_) }
  Remove-Item -LiteralPath $raw -Force
}
if (-not $rc) { $rc = 0 }
Write-Log "inject: exit $rc"
Write-Log "=== end ==="
exit $rc

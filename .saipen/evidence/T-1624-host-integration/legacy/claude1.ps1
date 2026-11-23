# SAIPEN emergency launch helper for the Claude Code CLI.
#
# The separated host-authority broker cannot authenticate a same-user Claude Code
# prompt hook on this machine, so mechanical admission is UNAVAILABLE. This helper
# sets the operator's EXPLICIT degraded policy through the canonical owner
# (`saipen authority mode degraded`), launches the ordinary `claude` CLI in the
# bound project, and says plainly that the session is DEGRADED / admission
# UNVERIFIED. It fabricates nothing: no admission ledger record, no runtime
# provenance marker, no host authority. The real Claude config and account are
# used unchanged (no --config-dir, no environment override).
param(
    [string]$ProjectRoot = "V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ClaudeArgs
)

$ErrorActionPreference = "Stop"

$SaipenRoot = "V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN"
$SaipenCmd = Join-Path $SaipenRoot "bin\saipen.cmd"

function Stop-Helper {
    param([string]$Message)
    Write-Host ""
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot ".saipen\STATE.md"))) {
    Stop-Helper "not a bound SAIPEN project: $ProjectRoot"
}

$claude = Get-Command "claude" -ErrorAction SilentlyContinue
if (-not $claude) {
    Stop-Helper "the Claude Code CLI executable 'claude' is not on PATH."
}

# Explicit, operator-owned policy. The canonical owner writes it; this script
# only asks for it. Anything other than this exact code leaves the mode alone.
$modeOut = (& $SaipenCmd authority mode degraded 2>&1 | Out-String)
if ($LASTEXITCODE -ne 0 -or $modeOut -notmatch "AUTHORITY_MODE_SET") {
    Stop-Helper "could not set the degraded authority policy: $($modeOut.Trim())"
}

Write-Host ""
Write-Host "SAIPEN DEGRADED - host admission unverified" -ForegroundColor Yellow
Write-Host "  project : $ProjectRoot"
Write-Host "  claude  : $($claude.Source)"
Write-Host "  policy  : degraded (explicit operator choice; NOT mechanical admission)"
Write-Host ""

Set-Location -LiteralPath $ProjectRoot

& $claude.Source @ClaudeArgs
exit $LASTEXITCODE

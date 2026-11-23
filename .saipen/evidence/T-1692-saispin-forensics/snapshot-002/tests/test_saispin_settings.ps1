param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition))
)

$ErrorActionPreference = 'Stop'
$fails = 0
function Check([string]$Name, [bool]$Ok, [string]$Detail = '') {
    if ($Ok) { Write-Host "PASS  $Name" }
    else { Write-Host "FAIL  $Name $Detail"; $script:fails++ }
}

$settingsScript = Join-Path $RepoRoot 'Scripts\saispin_settings.ps1'
$watcher = Join-Path $RepoRoot 'Scripts\saispin_watch.ps1'
$testRoot = Join-Path $env:TEMP ('saispin_settings_test_' + [Guid]::NewGuid().ToString('N'))
$config = Join-Path $testRoot 'settings.json'
$state = Join-Path $testRoot 'state.json'
$log = Join-Path $testRoot 'watch.log'
$notify = Join-Path $testRoot 'notify.json'
$layoutImage = Join-Path $testRoot 'layout.png'
$powerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'

try {
    New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
    $self = & $powerShellExe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $settingsScript -SelfTest 2>&1
    $selfExit = $LASTEXITCODE
    Check 'settings self-test validates round-trip and malformed defaults' ($selfExit -eq 0 -and (($self | Out-String) -match 'SAISPIN_SETTINGS_SELFTEST: PASS')) (($self | Out-String).Trim())

    $settings = [ordered]@{
        schema_version = 1
        thresholds = @{ cpu_percent = 80; required_hits = 6; minimum_hot_minutes = 30 }
        timing = @{ sample_seconds = 1; sweep_interval_minutes = 5; stale_gap_minutes = 30 }
        notifications = @{ enabled = $true; reminder_minutes = 60 }
        allowlist = @('Safe.exe')
        process_rules = @{ 'worker.exe' = @{ mode = 'alert_only' } }
    } | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($config, $settings, (New-Object Text.UTF8Encoding($false)))
    $layout = & $powerShellExe -NoLogo -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File $settingsScript -SelfTestLayout -ConfigFile $config -LayoutCapturePath $layoutImage 2>&1
    $layoutExit = $LASTEXITCODE
    Check 'settings controls construct in the compact Golden Default layout' ($layoutExit -eq 0 -and (($layout | Out-String) -match 'SAISPIN_SETTINGS_LAYOUT: PASS')) (($layout | Out-String).Trim())
    Check 'settings window paints to a bitmap without becoming visible' (Test-Path -LiteralPath $layoutImage)
    $sweep = & $powerShellExe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $watcher `
        -TestSweep -ConfigFile $config -StateFile $state -LogFile $log -NotifyFile $notify 2>&1
    $sweepExit = $LASTEXITCODE
    $sweepText = ($sweep | ForEach-Object { "$_" }) -join "`n"
    Check 'Test Sweep reports sampled, suspicious, alert and zero-kill counts' ($sweepExit -eq 0 -and $sweepText -match 'TEST SWEEP: sampled=\d+ suspicious=\d+ alerts=\d+ kills=0 \(dry-run\)') $sweepText
    Check 'Test Sweep does not write state, notification ledger or log' (-not (Test-Path $state) -and -not (Test-Path $notify) -and -not (Test-Path $log))

    $uiSweep = & $powerShellExe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $settingsScript -TestSweepUi -ConfigFile $config 2>&1
    $uiSweepExit = $LASTEXITCODE
    Check 'settings GUI Test Sweep executes asynchronously with diagnostics and unsaved UI handling' ($uiSweepExit -eq 0 -and (($uiSweep | Out-String) -match 'SAISPIN_SETTINGS_SWEEP_UI: PASS')) (($uiSweep | Out-String).Trim())

    $settingsText = Get-Content -Raw -LiteralPath $settingsScript
    Check 'Auto-kill arm requires explicit confirmation' ($settingsText.Contains('Confirm Auto-kill') -and $settingsText.Contains('modeArmConfirmed'))
    Check 'settings use atomic replacement and the existing task installer' ($settingsText.Contains('[IO.File]::Replace') -and $settingsText.Contains('$Installer'))
    Check 'failed settings or task rollback is visibly marked as a mismatch' ($settingsText.Contains('CONFIG_TASK_MISMATCH: task rollback failed') -and $settingsText.Contains('CONFIG_TASK_MISMATCH: settings rollback failed'))
    Check 'settings launcher does not request elevation' (-not $settingsText.Contains('Verb = ''runas''') -and -not $settingsText.Contains('Verb = "runas"'))
} finally {
    if (Test-Path -LiteralPath $testRoot) { Remove-Item -LiteralPath $testRoot -Recurse -Force }
}

Write-Host "---"
if ($fails -eq 0) { Write-Host 'SAISPIN_SETTINGS: PASS'; exit 0 }
Write-Host "SAISPIN_SETTINGS: FAIL ($fails failures)"
exit 1

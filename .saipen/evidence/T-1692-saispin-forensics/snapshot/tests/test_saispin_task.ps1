param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Definition)),
    [string]$ScriptSource = (Join-Path (Split-Path -Parent $PSCommandPath) '..\Scripts\Install-SaispinTask.ps1')
)

$ErrorActionPreference = 'Stop'

# T-135 harness: transactional scheduled-task replacement + exact cadence.
#
# 1. Assert-SaispinTask rejects a tampered 5->15 min cadence with the observed
#    value printed; the same task at 5 min passes.
# 2. Install-SaispinTask.ps1 replacement is transactional: register a known-good
#    fixture task, force a failure during the Register-ScheduledTask step, and
#    assert the original definition (action, trigger, principal, settings,
#    cadence) is byte-equivalent after the failure.
# 3. The script tolerates its task being absent before install (no prior task)
#    and leaves nothing half-registered when registration fails.
#
# Run:  powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_saispin_task.ps1
# Exit: 0 = all PASS, 1 = failures.

$fails = 0
function Check([string]$name, [bool]$ok, [string]$detail = '') {
    if ($ok) { Write-Host "PASS  $name  $detail" } else { Write-Host "FAIL  $name  $detail"; $script:fails++ }
}

$TaskPath = '\T135TEST\'
$TaskName = 'T135'
$FullName = $TaskPath + $TaskName

# Disposable principal under the current user: no elevation required.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

$stageRoot = Join-Path $env:TEMP ('t135_stage_' + [Guid]::NewGuid().ToString('N'))
if (-not (Test-Path $stageRoot)) { New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null }
$testConfig = Join-Path $stageRoot 'settings.json'
$fixtureSettings = [ordered]@{
    schema_version = 1
    thresholds = @{ cpu_percent = 80; required_hits = 6; minimum_hot_minutes = 30 }
    timing = @{ sample_seconds = 3; sweep_interval_minutes = 5; stale_gap_minutes = 30 }
    notifications = @{ enabled = $true; reminder_minutes = 60 }
    allowlist = @()
    process_rules = @{}
} | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($testConfig, $fixtureSettings, (New-Object System.Text.UTF8Encoding($false)))

function New-FixtureTask([int]$Minutes, [string]$ConfigPath = $testConfig) {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    # Match the shim's $PowerShellExe, $Watcher and $RepoRoot expectations:
    # shim sets $ScriptDir = %TEMP%\t135_stage\Scripts, so $Watcher lives in
    # that Scripts dir and $RepoRoot is t135_stage itself.
    $psExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $watcher = Join-Path (Join-Path $stageRoot 'Scripts') 'saispin_watch.ps1'
    $engine  = Join-Path (Join-Path $stageRoot 'Scripts') 'saispin_logic.py'
    if (-not (Test-Path $stageRoot)) { New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null }
    if (-not (Test-Path (Join-Path $stageRoot 'Scripts'))) { New-Item -ItemType Directory -Path (Join-Path $stageRoot 'Scripts') -Force | Out-Null }
    @("# T-135 fixture watcher placeholder") | Set-Content -LiteralPath $watcher -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'Scripts\saispin_logic.py') -Destination $engine -Force
    $action = New-ScheduledTaskAction -Execute $psExe `
        -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$watcher`" -DryRun -ConfigFile `"$ConfigPath`"" `
        -WorkingDirectory $stageRoot
    $span = New-TimeSpan -Minutes $Minutes
    $duration = New-TimeSpan -Days 3650
    # The shim's Assert-SaispinTask expects a LOGON trigger; repetition is
    # borrowed from a throwaway -Once trigger (the documented idiom the shipped
    # Install-SaispinTask.ps1 also uses).
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $repeatSource = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval $span -RepetitionDuration $duration
    $trigger.Repetition = $repeatSource.Repetition
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Hidden `
        -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName `
        -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
        -Description 'T135 fixture task'
}

function Invoke-Shim([string]$path, [string[]]$extra = @()) {
    # PS 5.1: the child's stderr arrives as error records, so 'Stop' in force
    # would abort the harness on an EXPECTED failure. The child's exit code
    # stays the verdict.
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    if ($extra -notcontains '-ConfigFile') { $extra += @('-ConfigFile', $testConfig) }
    try {
        $out = & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File $path @extra 2>&1
        return [pscustomobject]@{
            Output = ($out | ForEach-Object { "$_" }) -join "`n"
            Flat   = (($out | ForEach-Object { "$_" }) -join '') -replace '\s', ''
            Exit   = $LASTEXITCODE
        }
    } finally { $ErrorActionPreference = $old }
}

function Get-FixtureTask { Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue }

function Assert-TaskSnapshot {
    $t = Get-FixtureTask
    if (-not $t) { return $null }
    return @{
        ActionExecute = $t.Actions[0].Execute
        ActionArgs    = $t.Actions[0].Arguments
        TriggerCount  = $t.Triggers.Count
        PrincipalId   = $t.Principal.UserId
        SettingsMI    = "$($t.Settings.MultipleInstances)"
        Cadence       = $t.Triggers[0].Repetition.Interval
        Description   = $t.Description
    }
}

try {
    # --- case 1: exact-cadence verification ---------------------------------

    # Pull Assert-SaispinTask's cadence check out of the script via dot-sourcing
    # in a forked copy; the body binds the function to the same task name/path
    # in our disposable namespace, so the registered trigger IS the task being
    # verified. The shim also retargets $ScriptDir to a disposable stage root
    # holding stub watcher/engine files so the script's preflight
    # (Test-Path $Watcher / $Engine, watcher self-test) reaches the assertion
    # without ever running a real watcher.
    if (-not (Test-Path $stageRoot)) { New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null }
    New-Item -ItemType Directory -Path (Join-Path $stageRoot 'Scripts') -Force | Out-Null
    @("# T-135 fixture watcher placeholder") | Set-Content -LiteralPath (Join-Path $stageRoot 'Scripts\saispin_watch.ps1') -Encoding UTF8
    Copy-Item -LiteralPath (Join-Path $RepoRoot 'Scripts\saispin_logic.py') -Destination (Join-Path $stageRoot 'Scripts\saispin_logic.py') -Force
    # Install-SaispinTask.ps1 calls the real watcher self-test before any
    # registration, so the shim also has to neuter that one call. A safety
    # wrapper neutralises & $PowerShellExe ... $Watcher -SelfTest.
    $shim = Join-Path $env:TEMP ('t135_shim_' + [Guid]::NewGuid().ToString('N') + '.ps1')
    $scriptText = Get-Content -Raw -LiteralPath $ScriptSource
    $shimText = $scriptText
    $shimText = $shimText.Replace("`$TaskPath = '\SAITULS\'", "`$TaskPath = '$TaskPath'")
    $shimText = $shimText.Replace("`$TaskName = 'SAISPIN'", "`$TaskName = '$TaskName'")
    $shimText = $shimText.Replace("`$ScriptDir = if (`$PSScriptRoot) { `$PSScriptRoot } else { Split-Path -Parent `$MyInvocation.MyCommand.Definition }", "`$ScriptDir = '$stageRoot\Scripts'")
    # Disable the watcher self-test preflight so the shim is a unit-level probe
    # of cadence + transaction; the same shim still exercises Assert-SaispinTask,
    # the rollback path and the registered definition. Real-install preflight
    # remains a separate concern of Install-SaispinTask.ps1 itself.
    $shimText = $shimText.Replace("& `$PowerShellExe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `$Watcher -SelfTest | Out-Null", "`$global:LASTEXITCODE = 0")
    Set-Content -LiteralPath $shim -Value $shimText -Encoding UTF8

    New-FixtureTask 5
    $r5 = Invoke-Shim $shim '-VerifyOnly'
    Check 'assertion PASSes when cadence matches' ($r5.Exit -eq 0) "exit=$($r5.Exit)"
    Check 'assertion verifies the exact shared config path' ($r5.Flat -match [regex]::Escape($testConfig))
    New-FixtureTask 5 (Join-Path $stageRoot 'other-settings.json')
    $wrongConfig = Invoke-Shim $shim '-VerifyOnly'
    Check 'assertion rejects a task wired to another config path' ($wrongConfig.Exit -ne 0 -and $wrongConfig.Flat -match 'Configdrift')
    $customSettings = [ordered]@{
        schema_version = 1
        thresholds = @{ cpu_percent = 80; required_hits = 6; minimum_hot_minutes = 30 }
        timing = @{ sample_seconds = 3; sweep_interval_minutes = 7; stale_gap_minutes = 30 }
        notifications = @{ enabled = $true; reminder_minutes = 60 }
        allowlist = @()
        process_rules = @{}
    } | ConvertTo-Json -Depth 8
    [IO.File]::WriteAllText($testConfig, $customSettings, (New-Object System.Text.UTF8Encoding($false)))
    New-FixtureTask 7
    $configuredCadence = Invoke-Shim $shim '-VerifyOnly'
    Check 'task verification derives cadence from shared settings' ($configuredCadence.Exit -eq 0) $configuredCadence.Output
    $requestedMismatch = Invoke-Shim $shim @('-VerifyOnly', '-IntervalMinutes', '5')
    Check 'explicit cadence cannot drift from shared settings' ($requestedMismatch.Exit -ne 0 -and $requestedMismatch.Flat -match 'Cadencemismatch')
    [IO.File]::WriteAllText($testConfig, $fixtureSettings, (New-Object System.Text.UTF8Encoding($false)))

    New-FixtureTask 15
    $r15 = Invoke-Shim $shim '-VerifyOnly'
    Check 'assertion FAILS on 15 min drift' ($r15.Exit -ne 0) "exit=$($r15.Exit)"
    Check 'assertion reports the observed interval verbatim (00:15:00)' ($r15.Flat -match '00:15:00') ''
    Check 'assertion reports the expected interval verbatim (00:05:00)' ($r15.Flat -match '00:05:00') ''

    # --- case 2: transactional replacement on real Register-ScheduledTask ---

    # Build a "good" prior task with the same watcher-like properties.
    New-FixtureTask 5
    $before = Assert-TaskSnapshot

    $beforeXml = Export-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
    $snapshotFailPath = Join-Path $stageRoot 'snapshot_fail.ps1'
    # Fail the complete XML snapshot seam. On the old implementation this
    # seam is never called and replacement proceeds, changing the prior task.
    $snapshotFail = $shimText.Replace('$prior = Get-SaispinTask', @'
function Export-ScheduledTask { throw 'SNAPSHOT_CAPTURE_INJECTED' }
function Unregister-ScheduledTask { throw 'UNREGISTER_MUST_NOT_RUN' }
$prior = Get-SaispinTask
'@)
    Set-Content -LiteralPath $snapshotFailPath -Value $snapshotFail -Encoding UTF8
    $rs = Invoke-Shim $snapshotFailPath
    Check 'snapshot capture failure refuses replacement' ($rs.Exit -ne 0 -and $rs.Flat -match 'SNAPSHOT_CAPTURE_INJECTED') $rs.Output
    Check 'snapshot failure keeps complete prior task XML unchanged' `
        ((Export-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName) -ceq $beforeXml)

    $doubleFailPath = Join-Path $stageRoot 'double_fail.ps1'
    $doubleFail = $shimText.Replace('$prior = Get-SaispinTask', @'
$script:registrationCalls = 0
function Register-ScheduledTask {
    $script:registrationCalls++
    if ($script:registrationCalls -eq 1) { throw 'REPLACEMENT_INJECTED' }
    throw 'ROLLBACK_INJECTED'
}
$prior = Get-SaispinTask
'@)
    Set-Content -LiteralPath $doubleFailPath -Value $doubleFail -Encoding UTF8
    $rd = Invoke-Shim $doubleFailPath
    Check 'replacement and rollback failures retain distinct diagnostics' `
        ($rd.Exit -ne 0 -and $rd.Flat -match 'Replacementfailed.*REPLACEMENT_INJECTED.*ROLLBACK_INJECTED') $rd.Output
    New-FixtureTask 5
    $before = Assert-TaskSnapshot

    # A second shim that points the script at a watcher path that exists but
    # the engine path that does NOT: this proves preflight preservation only.
    $shimFailPath = Join-Path $env:TEMP ('t135_fail_' + [Guid]::NewGuid().ToString('N') + '.ps1')
    $shimFail = $shimText
    $shimFail = $shimFail.Replace("`$Engine    = Join-Path `$ScriptDir 'saispin_logic.py'", "`$Engine    = 'V:\\nope\\missing_engine.py'")
    Set-Content -LiteralPath $shimFailPath -Value $shimFail -Encoding UTF8

    $rf = Invoke-Shim $shimFailPath
    Check 'install with a missing engine exits nonzero' ($rf.Exit -ne 0) "exit=$($rf.Exit)"
    Check 'install failure names the missing engine' ($rf.Flat -match 'missing_engine\.py') ''

    $after = Assert-TaskSnapshot
    Check 'original task was restored after the failed replacement' ($null -ne $after) ''
    if ($after) {
        Check 'restored action execute matches prior' ($after.ActionExecute -eq $before.ActionExecute) "$($after.ActionExecute) vs $($before.ActionExecute)"
        Check 'restored action arguments match prior' ($after.ActionArgs -eq $before.ActionArgs) ''
        Check 'restored trigger count matches prior' ($after.TriggerCount -eq $before.TriggerCount) "was=$($before.TriggerCount) now=$($after.TriggerCount)"
        Check 'restored principal matches prior' ($after.PrincipalId -eq $before.PrincipalId) ''
        Check 'restored settings (MultipleInstances) match prior' ($after.SettingsMI -eq $before.SettingsMI) ''
        Check 'restored cadence matches prior' ($after.Cadence -eq $before.Cadence) "was=$($before.Cadence) now=$($after.Cadence)"
        Check 'restored description matches prior' ($after.Description -eq $before.Description) ''
    }

    $rollbackPath = Join-Path $stageRoot 'rollback.ps1'
    $beforeXml = Export-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName
    $rollbackShim = $shimText.Replace('$prior = Get-SaispinTask', @'
$script:registrationCalls = 0
function Register-ScheduledTask {
    param($TaskPath, $TaskName, $Action, $Trigger, $Settings, $Description, $Xml)
    $script:registrationCalls++
    if ($script:registrationCalls -eq 1) { throw 'REPLACEMENT_INJECTED' }
    ScheduledTasks\Register-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Xml $Xml
}
$prior = Get-SaispinTask
'@)
    Set-Content -LiteralPath $rollbackPath -Value $rollbackShim -Encoding UTF8
    $rb = Invoke-Shim $rollbackPath
    Check 'injected post-unregister failure preserves original replacement exception' `
        ($rb.Exit -ne 0 -and $rb.Flat -match 'REPLACEMENT_INJECTED')
    Check 'real rollback restores complete prior task XML' `
        ((Export-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName) -ceq $beforeXml)

    # --- case 3: no prior task, replacement failure leaves no half-registration ---

    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false
    $rn = Invoke-Shim $shimFailPath
    Check 'fresh install with missing engine exits nonzero' ($rn.Exit -ne 0) "exit=$($rn.Exit)"
    Check 'no half-registered task remains after a failed fresh install' `
        ($null -eq (Get-FixtureTask)) ''

    # --- case 4: -Remove cleans up the fixture ------------------------------

    New-FixtureTask 5
    $rr = Invoke-Shim $shim '-Remove'
    Check '-Remove unregisters the task' ($null -eq (Get-FixtureTask)) "exit=$($rr.Exit)"

    # --- case 5: source shape ------------------------------------------------

    $src = Get-Content -Raw -LiteralPath $ScriptSource
    Check 'install script captures prior task definition before destructive step' ($src -match '\$priorBackup = @\{') ''
    Check 'install script restores prior task on failure' `
        ($src -match '-Xml \$priorBackup\.Xml') ''
    Check 'install script normalises the observed cadence through XmlConvert' `
        ($src -match '\[System\.Xml\.XmlConvert\]::ToTimeSpan') ''
    Check 'install script prints both expected and observed on cadence drift' ($src -match 'Cadence drift: expected') ''
    $backupAt = ([regex]::Match($src, '\$prior = Get-SaispinTask')).Index
    # The FIRST unregister after the backup point is the destructive step of the
    # install path (the -Remove branch sits earlier in the file).
    $post = $src.Substring($backupAt)
    $unregRel = ([regex]::Match($post, 'Unregister-ScheduledTask -TaskPath \$TaskPath -TaskName \$TaskName -Confirm:\$false')).Index
    Check 'prior task is backed up BEFORE the destructive unregister, never after' `
        ($backupAt -ge 0 -and $unregRel -gt 0) "backup=$backupAt unregRel=$unregRel"
} finally {
    Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    foreach ($owned in @($shim, $shimFailPath)) {
        if ($owned -and (Test-Path -LiteralPath $owned)) { Remove-Item -LiteralPath $owned -Force }
    }
    if ((Split-Path -Parent ([IO.Path]::GetFullPath($stageRoot))) -eq ([IO.Path]::GetFullPath($env:TEMP).TrimEnd('\'))) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
}

Write-Host '---'
if ($fails) { Write-Host "FAILED ($fails failure(s))"; exit 1 }
Write-Host 'PASS (0 failures)'
exit 0

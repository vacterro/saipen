<#
.SYNOPSIS
    SAISPIN policy and scheduled-task settings.

.DESCRIPTION
    Edits the per-user SAISPIN policy, validates it through the shared Python
    engine, then updates the scheduled task through its transactional installer.
    Test Sweep is permanently dry-run and does not write watchdog state.
#>
[CmdletBinding()]
param(
    [switch]$SelfTest,
    [switch]$SelfTestLayout,
    [switch]$TestSweepUi,
    [string]$ConfigFile,
    [string]$LayoutCapturePath
)

$ErrorActionPreference = 'Stop'
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$RepoRoot = Split-Path -Parent $ScriptDir
$Engine = Join-Path $ScriptDir 'saispin_logic.py'
$Watcher = Join-Path $ScriptDir 'saispin_watch.ps1'
$Installer = Join-Path $ScriptDir 'Install-SaispinTask.ps1'
$PowerShellExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not $ConfigFile) {
    $ConfigRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
    $ConfigFile = Join-Path $ConfigRoot 'SAITULS\SAISPIN\settings.json'
}
$ConfigFile = [IO.Path]::GetFullPath($ConfigFile)
$LogFile = Join-Path (Split-Path -Parent $ConfigFile) 'saispin.log'

function Write-AtomicText {
    param([string]$Path, [string]$Text)
    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $temporary = Join-Path $directory ('.settings-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllText($temporary, $Text, (New-Object System.Text.UTF8Encoding($false)))
        if ([IO.File]::Exists($Path)) {
            [IO.File]::Replace($temporary, $Path, $null)
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Write-AtomicBytes {
    param([string]$Path, [byte[]]$Bytes)
    $directory = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $directory)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $temporary = Join-Path $directory ('.settings-' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        [IO.File]::WriteAllBytes($temporary, $Bytes)
        if ([IO.File]::Exists($Path)) {
            [IO.File]::Replace($temporary, $Path, $null)
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Invoke-SettingsNormalizer {
    param([string]$Path)
    if ($Path) { $output = & python $Engine --normalize-settings $Path 2>&1 }
    else { $output = & python $Engine --normalize-settings --defaults 2>&1 }
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw ('Policy validation failed (exit ' + $code + '): ' + ($output -join ' ')) }
    return (($output | Out-String) | ConvertFrom-Json)
}

function Test-SettingsAssert {
    param([bool]$Condition, [string]$Name)
    if (-not $Condition) { throw ('FAIL: ' + $Name) }
    Write-Output ('PASS: ' + $Name)
}

if ($SelfTest) {
    $work = Join-Path $env:TEMP ('saispin_settings_test_' + [Guid]::NewGuid().ToString('N'))
    $testConfig = Join-Path $work 'settings.json'
    try {
        New-Item -ItemType Directory -Path $work -Force | Out-Null
        $roundTrip = [ordered]@{
            schema_version = 1
            thresholds = @{ cpu_percent = 91; required_hits = 7; minimum_hot_minutes = 35 }
            timing = @{ sample_seconds = 4; sweep_interval_minutes = 7; stale_gap_minutes = 35 }
            notifications = @{ enabled = $false; reminder_minutes = 90 }
            allowlist = @('Example.exe')
            process_rules = @{ 'worker.exe' = @{ mode = 'alert_only'; cpu_percent = 95 } }
        } | ConvertTo-Json -Depth 8
        Write-AtomicText -Path $testConfig -Text $roundTrip
        $loaded = Invoke-SettingsNormalizer -Path $testConfig
        Test-SettingsAssert ($null -eq $loaded.warning) 'valid settings normalize without warnings'
        Test-SettingsAssert ($loaded.settings.thresholds.required_hits -eq 7) 'thresholds survive JSON round-trip'
        Test-SettingsAssert ($loaded.settings.allowlist[0] -eq 'example.exe') 'allowlist is normalized case-insensitively'
        Test-SettingsAssert ($loaded.settings.process_rules.'worker.exe'.mode -eq 'alert_only') 'alert-only process rule survives round-trip'
        $badConfig = Join-Path $work 'bad.json'
        Write-AtomicText -Path $badConfig -Text '{"thresholds":{"required_hits":0},"allowlist":["unsafe.exe"]}'
        $bad = Invoke-SettingsNormalizer -Path $badConfig
        Test-SettingsAssert ($bad.warning -and $bad.settings.thresholds.required_hits -eq 6 -and $bad.settings.allowlist.Count -eq 0) 'malformed settings fail closed to complete defaults'
        Write-Output 'SAISPIN_SETTINGS_SELFTEST: PASS'
        exit 0
    } catch {
        Write-Output ('SAISPIN_SETTINGS_SELFTEST: FAIL: ' + $_.Exception.Message)
        exit 1
    } finally {
        if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
    }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
foreach ($required in @($Engine, $Watcher, $Installer)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        [System.Windows.Forms.MessageBox]::Show("SAISPIN file is missing:`n$required", 'SAISPIN Settings') | Out-Null
        exit 1
    }
}

$Palette = @{
    Background = [System.Drawing.Color]::FromArgb(0x1A, 0x18, 0x10)
    Surface = [System.Drawing.Color]::FromArgb(0x33, 0x2E, 0x22)
    Raised = [System.Drawing.Color]::FromArgb(0x3D, 0x37, 0x2A)
    Alternate = [System.Drawing.Color]::FromArgb(0x45, 0x3D, 0x30)
    Bevel = [System.Drawing.Color]::FromArgb(0x75, 0x66, 0x3D)
    Border = [System.Drawing.Color]::FromArgb(0x10, 0x0E, 0x08)
    Highlight = [System.Drawing.Color]::FromArgb(0xF0, 0xD0, 0x60)
    Text = [System.Drawing.Color]::FromArgb(0xD4, 0xC8, 0x9A)
    Secondary = [System.Drawing.Color]::FromArgb(0x9C, 0x93, 0x71)
    Danger = [System.Drawing.Color]::FromArgb(0xD6, 0x64, 0x64)
}
$uiFont = New-Object System.Drawing.Font('Verdana', 8.0)

function Set-ControlStyle {
    param($Control, [bool]$Raised = $false)
    $Control.Font = $uiFont
    $Control.ForeColor = $Palette.Text
    $Control.BackColor = if ($Raised) { $Palette.Raised } else { $Palette.Surface }
}

function New-UiLabel {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width = 130)
    $control = New-Object System.Windows.Forms.Label
    $control.Text = $Text
    $control.Location = New-Object System.Drawing.Point($X, $Y)
    $control.Size = New-Object System.Drawing.Size($Width, 20)
    $control.TextAlign = [System.Drawing.ContentAlignment]::MiddleLeft
    Set-ControlStyle $control
    return $control
}

function New-UiNumber {
    param([int]$X, [int]$Y, [int]$Minimum, [int]$Maximum)
    $control = New-Object System.Windows.Forms.NumericUpDown
    $control.Location = New-Object System.Drawing.Point($X, $Y)
    $control.Size = New-Object System.Drawing.Size(64, 22)
    $control.Minimum = $Minimum
    $control.Maximum = $Maximum
    $control.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
    Set-ControlStyle $control $true
    return $control
}

function New-UiButton {
    param([string]$Text, [int]$X, [int]$Y, [int]$Width)
    $control = New-Object System.Windows.Forms.Button
    $control.Text = $Text
    $control.Location = New-Object System.Drawing.Point($X, $Y)
    $control.Size = New-Object System.Drawing.Size($Width, 27)
    $control.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $control.FlatAppearance.BorderColor = $Palette.Bevel
    $control.FlatAppearance.BorderSize = 2
    Set-ControlStyle $control $true
    return $control
}

function Get-TaskStatus {
    $result = [ordered]@{
        Exists = $false
        AutoKill = $false
        IntervalMinutes = 5
        StatusCode = 'NOT_INSTALLED'
        LastRunTime = $null
        LastTaskResult = $null
        Text = 'Scheduled: NO (NOT_INSTALLED) | Mode: DRY-RUN'
    }
    try {
        if (-not (Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)) {
            $result.StatusCode = 'NOT_INSTALLED'
            $result.Text = 'Scheduled task status unavailable'
            return $result
        }
        $task = Get-ScheduledTask -TaskPath '\SAITULS\' -TaskName 'SAISPIN' -ErrorAction SilentlyContinue
        if (-not $task) {
            $result.StatusCode = 'NOT_INSTALLED'
            $result.Text = 'Scheduled: NO (NOT_INSTALLED) | Mode: DRY-RUN'
            return $result
        }
        $result.Exists = $true
        $arguments = [string]$task.Actions[0].Arguments
        $result.AutoKill = $arguments -match '(?i)(^|\s)-AutoKill(\s|$)'
        $match = [regex]::Match($arguments, '(?i)-ConfigFile\s+"([^"]+)"')
        $configMismatch = -not $match.Success -or -not [string]::Equals([IO.Path]::GetFullPath($match.Groups[1].Value), $ConfigFile, [StringComparison]::OrdinalIgnoreCase)

        foreach ($trigger in $task.Triggers) {
            if ($trigger.Repetition.Interval) {
                try {
                    $span = [System.Xml.XmlConvert]::ToTimeSpan($trigger.Repetition.Interval)
                    if ($span.TotalMinutes -ge 1) { $result.IntervalMinutes = [int]$span.TotalMinutes }
                } catch { }
                break
            }
        }

        $info = $null
        try {
            $info = Get-ScheduledTaskInfo -TaskPath '\SAITULS\' -TaskName 'SAISPIN' -ErrorAction SilentlyContinue
            if ($info) {
                $result.LastRunTime = $info.LastRunTime
                $result.LastTaskResult = $info.LastTaskResult
            }
        } catch { }

        if ($configMismatch) {
            $result.StatusCode = 'CONFIG_TASK_MISMATCH'
            $result.Text = 'CONFIG_TASK_MISMATCH: task uses another settings file'
        } elseif ($task.State -eq 'Disabled') {
            $result.StatusCode = 'INSTALLED_DISABLED'
            $result.Text = 'Scheduled: YES (INSTALLED_DISABLED) | Mode: ' + $(if ($result.AutoKill) { 'AUTO-KILL' } else { 'DRY-RUN' })
        } elseif ($task.State -eq 'Running') {
            $result.StatusCode = 'RUNNING'
            $result.Text = 'Scheduled: YES (RUNNING) | Mode: ' + $(if ($result.AutoKill) { 'AUTO-KILL' } else { 'DRY-RUN' })
        } elseif ($info -and $info.LastTaskResult -ne 0 -and $info.LastTaskResult -ne 0x41301 -and $info.LastTaskResult -ne 267009 -and $info.LastRunTime -and $info.LastRunTime.Year -gt 2000) {
            $result.StatusCode = 'TASK_FAILED'
            $result.Text = 'TASK_FAILED (0x' + $info.LastTaskResult.ToString('X') + '): ' + (Get-Date $info.LastRunTime -Format 'HH:mm:ss')
        } else {
            $result.StatusCode = if ($result.AutoKill) { 'READY_AUTO_KILL' } else { 'READY_DRY_RUN' }
            $result.Text = 'Scheduled: YES | Mode: ' + $(if ($result.AutoKill) { 'AUTO-KILL' } else { 'DRY-RUN' }) +
                ' | Every ' + $result.IntervalMinutes + ' min'
        }
    } catch {
        $result.StatusCode = 'NOT_INSTALLED'
        $result.Text = 'Scheduled task status unavailable: ' + $_.Exception.Message
    }
    return $result
}

function ConvertFrom-TextLines {
    param([string]$Text)
    return @($Text -split "(`r`n|`n|`r)" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Get-ControlSettings {
    $allowlist = @(ConvertFrom-TextLines $allowlistBox.Text)
    $rules = [ordered]@{}
    foreach ($line in (ConvertFrom-TextLines $rulesBox.Text)) {
        $parts = @($line -split '\|' | ForEach-Object { $_.Trim() })
        if ($parts.Count -lt 2 -or $parts.Count -gt 5) {
            throw ('Process rule must be: image | default or alert_only | cpu | hits | minutes. Bad line: ' + $line)
        }
        $image = $parts[0]
        if (-not $image) { throw 'Process rule image name cannot be empty.' }
        $rule = [ordered]@{ mode = if ($parts[1]) { $parts[1].ToLowerInvariant() } else { 'default' } }
        $names = @('cpu_percent', 'required_hits', 'minimum_hot_minutes')
        for ($i = 2; $i -lt $parts.Count; $i++) {
            if ($parts[$i]) {
                $number = 0
                if (-not [int]::TryParse($parts[$i], [ref]$number)) {
                    throw ($names[$i - 2] + ' must be a whole number in process rule: ' + $line)
                }
                $rule[$names[$i - 2]] = $number
            }
        }
        $rules[$image] = $rule
    }
    return [ordered]@{
        schema_version = 1
        thresholds = [ordered]@{
            cpu_percent = [int]$cpuBox.Value
            required_hits = [int]$hitsBox.Value
            minimum_hot_minutes = [int]$minutesBox.Value
        }
        timing = [ordered]@{
            sample_seconds = [int]$sampleBox.Value
            sweep_interval_minutes = [int]$intervalBox.Value
            stale_gap_minutes = [int]$staleBox.Value
        }
        notifications = [ordered]@{
            enabled = [bool]$notifyBox.Checked
            reminder_minutes = [int]$reminderBox.Value
        }
        allowlist = $allowlist
        process_rules = $rules
    }
}

$status = Get-TaskStatus
try {
    if (Test-Path -LiteralPath $ConfigFile -PathType Leaf) {
        $normalized = Invoke-SettingsNormalizer -Path $ConfigFile
    } else {
        $normalized = Invoke-SettingsNormalizer
    }
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        'SAISPIN policy could not be loaded. Install Python or repair the settings engine.' +
        [Environment]::NewLine + $_.Exception.Message,
        'SAISPIN Settings', [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    exit 1
}
if ($normalized.warning) {
    [System.Windows.Forms.MessageBox]::Show(
        'Settings could not be read; safe defaults are loaded. Save to replace them.' + [Environment]::NewLine + $normalized.warning,
        'SAISPIN Settings', [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
}
$current = $normalized.settings

$form = New-Object System.Windows.Forms.Form
$form.Text = 'SAISPIN Settings'
$form.ClientSize = New-Object System.Drawing.Size(430, 400)
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.MaximizeBox = $false
$form.MinimizeBox = $false
$form.BackColor = $Palette.Background
$form.ForeColor = $Palette.Text
$form.Font = $uiFont
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None

$statusLabel = New-UiLabel $status.Text 10 8 410
$statusLabel.ForeColor = if ($status.Text.StartsWith('CONFIG_TASK_MISMATCH')) { $Palette.Danger } else { $Palette.Secondary }
$form.Controls.Add($statusLabel)

$tabs = New-Object System.Windows.Forms.TabControl
$tabs.Location = New-Object System.Drawing.Point(10, 34)
$tabs.Size = New-Object System.Drawing.Size(410, 250)
$tabs.Font = $uiFont
$tabs.BackColor = $Palette.Surface
$tabs.ForeColor = $Palette.Text
$tabs.DrawMode = [System.Windows.Forms.TabDrawMode]::OwnerDrawFixed
$tabs.add_DrawItem({
    param($sender, $event)
    $page = $sender.TabPages[$event.Index]
    $selected = $sender.SelectedIndex -eq $event.Index
    $fill = if ($selected) { $Palette.Raised } else { $Palette.Surface }
    $text = if ($selected) { $Palette.Highlight } else { $Palette.Secondary }
    $brush = New-Object System.Drawing.SolidBrush($fill)
    try {
        $event.Graphics.FillRectangle($brush, $event.Bounds)
    } finally {
        $brush.Dispose()
    }
    $flags = [System.Windows.Forms.TextFormatFlags]::HorizontalCenter -bor
        [System.Windows.Forms.TextFormatFlags]::VerticalCenter -bor
        [System.Windows.Forms.TextFormatFlags]::SingleLine -bor
        [System.Windows.Forms.TextFormatFlags]::NoPadding
    [System.Windows.Forms.TextRenderer]::DrawText(
        $event.Graphics, $page.Text, $uiFont, $event.Bounds, $text, $fill, $flags)
})
$form.Controls.Add($tabs)
$policyTab = New-Object System.Windows.Forms.TabPage('Detection')
$policyTab.UseVisualStyleBackColor = $false
$policyTab.BackColor = $Palette.Background
$policyTab.ForeColor = $Palette.Text
$processTab = New-Object System.Windows.Forms.TabPage('Process rules')
$processTab.UseVisualStyleBackColor = $false
$processTab.BackColor = $Palette.Background
$processTab.ForeColor = $Palette.Text
$tabs.TabPages.Add($policyTab)
$tabs.TabPages.Add($processTab)
foreach ($page in $tabs.TabPages) {
    $page.UseVisualStyleBackColor = $false
    $page.BackColor = $Palette.Background
}

$policyTab.Controls.Add((New-UiLabel 'CPU threshold (%)' 12 14 128))
$cpuBox = New-UiNumber 145 13 50 100
$cpuBox.Value = [decimal]$current.thresholds.cpu_percent
$policyTab.Controls.Add($cpuBox)
$policyTab.Controls.Add((New-UiLabel 'Hot hits' 220 14 92))
$hitsBox = New-UiNumber 315 13 2 60
$hitsBox.Value = [decimal]$current.thresholds.required_hits
$policyTab.Controls.Add($hitsBox)
$policyTab.Controls.Add((New-UiLabel 'Minimum hot (min)' 12 47 128))
$minutesBox = New-UiNumber 145 46 5 240
$minutesBox.Value = [decimal]$current.thresholds.minimum_hot_minutes
$policyTab.Controls.Add($minutesBox)
$policyTab.Controls.Add((New-UiLabel 'Sample (sec)' 220 47 95))
$sampleBox = New-UiNumber 315 46 1 30
$sampleBox.Value = [decimal]$current.timing.sample_seconds
$policyTab.Controls.Add($sampleBox)
$policyTab.Controls.Add((New-UiLabel 'Sweep interval (min)' 12 80 128))
$intervalBox = New-UiNumber 145 79 1 1440
$intervalBox.Value = [decimal]$current.timing.sweep_interval_minutes
$policyTab.Controls.Add($intervalBox)
$policyTab.Controls.Add((New-UiLabel 'Stale gap (min)' 220 80 95))
$staleBox = New-UiNumber 315 79 5 1440
$staleBox.Value = [decimal]$current.timing.stale_gap_minutes
$policyTab.Controls.Add($staleBox)
$policyTab.Controls.Add((New-UiLabel 'Reminder (min)' 12 113 128))
$reminderBox = New-UiNumber 145 112 5 1440
$reminderBox.Value = [decimal]$current.notifications.reminder_minutes
$policyTab.Controls.Add($reminderBox)
$notifyBox = New-Object System.Windows.Forms.CheckBox
$notifyBox.Text = 'Show tray notifications'
$notifyBox.Location = New-Object System.Drawing.Point(220, 111)
$notifyBox.Size = New-Object System.Drawing.Size(175, 24)
$notifyBox.Checked = [bool]$current.notifications.enabled
Set-ControlStyle $notifyBox
$policyTab.Controls.Add($notifyBox)
$policyTab.Controls.Add((New-UiLabel 'Threshold changes apply to new samples. System and identity guards stay on.' 12 158 375))

$processTab.Controls.Add((New-UiLabel 'Allowlist: one image name per line' 12 10 370))
$allowlistBox = New-Object System.Windows.Forms.TextBox
$allowlistBox.Multiline = $true
$allowlistBox.AcceptsReturn = $true
$allowlistBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$allowlistBox.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$allowlistBox.Location = New-Object System.Drawing.Point(12, 32)
$allowlistBox.Size = New-Object System.Drawing.Size(375, 50)
$allowlistBox.Text = [string]::Join([Environment]::NewLine, [string[]]$current.allowlist)
Set-ControlStyle $allowlistBox $true
$processTab.Controls.Add($allowlistBox)
$processTab.Controls.Add((New-UiLabel 'Rules: image | mode | cpu | hits | minutes' 12 91 375))
$rulesBox = New-Object System.Windows.Forms.TextBox
$rulesBox.Multiline = $true
$rulesBox.AcceptsReturn = $true
$rulesBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$rulesBox.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$rulesBox.Location = New-Object System.Drawing.Point(12, 113)
$rulesBox.Size = New-Object System.Drawing.Size(375, 84)
$ruleLines = New-Object 'System.Collections.Generic.List[string]'
foreach ($entry in $current.process_rules.PSObject.Properties) {
    $rule = $entry.Value
    $ruleLines.Add(($entry.Name + ' | ' + $rule.mode + ' | ' +
        $rule.cpu_percent + ' | ' + $rule.required_hits + ' | ' + $rule.minimum_hot_minutes).TrimEnd(' ', '|'))
}
$rulesBox.Text = [string]::Join([Environment]::NewLine, $ruleLines.ToArray())
Set-ControlStyle $rulesBox $true
$processTab.Controls.Add($rulesBox)
$processTab.Controls.Add((New-UiLabel 'Only stricter numeric rules are accepted; alert_only can never kill.' 12 201 375))

$modeBox = New-Object System.Windows.Forms.GroupBox
$modeBox.Text = 'Scheduled task mode'
$modeBox.Location = New-Object System.Drawing.Point(10, 289)
$modeBox.Size = New-Object System.Drawing.Size(248, 47)
$modeBox.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
Set-ControlStyle $modeBox
$dryRadio = New-Object System.Windows.Forms.RadioButton
$dryRadio.Text = 'Dry-run'
$dryRadio.Location = New-Object System.Drawing.Point(12, 18)
$dryRadio.Size = New-Object System.Drawing.Size(88, 22)
$dryRadio.Checked = -not [bool]$status.AutoKill
Set-ControlStyle $dryRadio
$autoRadio = New-Object System.Windows.Forms.RadioButton
$autoRadio.Text = 'Auto-kill'
$autoRadio.Location = New-Object System.Drawing.Point(112, 18)
$autoRadio.Size = New-Object System.Drawing.Size(100, 22)
$autoRadio.Checked = [bool]$status.AutoKill
Set-ControlStyle $autoRadio
$modeBox.Controls.Add($dryRadio)
$modeBox.Controls.Add($autoRadio)
$form.Controls.Add($modeBox)

$copyDiagButton = New-UiButton 'Copy diag' 268 298 72
$openLogButton = New-UiButton 'Open log' 346 298 74
$form.Controls.Add($copyDiagButton)
$form.Controls.Add($openLogButton)

$testButton = New-UiButton 'Test sweep' 10 344 98
$saveButton = New-UiButton 'Save' 278 344 66
$closeButton = New-UiButton 'Close' 352 344 68
$testStatus = New-UiLabel '' 116 347 152
$testStatus.ForeColor = $Palette.Secondary
$form.Controls.Add($testButton)
$form.Controls.Add($testStatus)
$form.Controls.Add($saveButton)
$form.Controls.Add($closeButton)
$resultLabel = New-UiLabel '' 10 376 410
$resultLabel.ForeColor = $Palette.Secondary
$form.Controls.Add($resultLabel)

$modeAutoAtOpen = [bool]$status.AutoKill
$script:modeArmConfirmed = $false
$autoRadio.add_CheckedChanged({
    if ($autoRadio.Checked -and -not $modeAutoAtOpen -and -not $script:modeArmConfirmed) {
        $answer = [System.Windows.Forms.MessageBox]::Show(
            'Auto-kill can terminate orphaned processes after every safety gate passes. Arm it?',
            'Confirm Auto-kill', [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Warning)
        if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {
            $script:modeArmConfirmed = $true
        } else {
            $dryRadio.Checked = $true
        }
    }
})

$script:TestRunspace = $null
$script:TestPs = $null
$script:TestAsyncResult = $null
$script:TestTimer = $null
$script:TestStartTime = $null
$script:TestTempConfig = $null
$script:TestIsUnsaved = $false
$script:LastDiagnostics = $null

function Clean-TestSweepResources {
    if ($script:TestTimer) {
        $script:TestTimer.Stop()
        $script:TestTimer.Dispose()
        $script:TestTimer = $null
    }
    if ($script:TestPs) {
        try { $script:TestPs.Stop() } catch { }
        try { $script:TestPs.Dispose() } catch { }
        $script:TestPs = $null
    }
    if ($script:TestRunspace) {
        try {
            if ($script:TestRunspace.RunspaceStateInfo.State -eq [System.Management.Automation.Runspaces.RunspaceState]::Opened) {
                $script:TestRunspace.Close()
            }
        } catch { }
        try { $script:TestRunspace.Dispose() } catch { }
        $script:TestRunspace = $null
    }
    if ($script:TestTempConfig -and [IO.File]::Exists($script:TestTempConfig)) {
        try { [IO.File]::Delete($script:TestTempConfig) } catch { }
    }
    $script:TestTempConfig = $null
    $script:TestAsyncResult = $null
}

function Set-ClipboardSafe([string]$Text) {
    if ([System.Threading.Thread]::CurrentThread.GetApartmentState() -eq [System.Threading.ApartmentState]::STA) {
        [System.Windows.Forms.Clipboard]::SetText($Text)
    } else {
        $staThread = New-Object System.Threading.Thread([System.Threading.ThreadStart]{
            [System.Windows.Forms.Clipboard]::SetText($Text)
        })
        $staThread.SetApartmentState([System.Threading.ApartmentState]::STA)
        $staThread.Start()
        $staThread.Join(2000)
    }
}

function Format-DiagnosticsReport {
    param(
        [string]$Status,
        [int]$ExitCode,
        [string]$Stdout,
        [string]$Stderr,
        [double]$DurationSeconds,
        [bool]$UnsavedUi
    )
    $lines = New-Object 'System.Collections.Generic.List[string]'
    $lines.Add('================================================================')
    $lines.Add('SAISPIN TEST SWEEP DIAGNOSTIC REPORT')
    $lines.Add('================================================================')
    $lines.Add(('Timestamp:       ' + (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')))
    $lines.Add(('Verdict:         ' + $Status))
    $lines.Add(('Exit Code:       ' + $ExitCode))
    $lines.Add(('Duration:        {0:N2}s' -f $DurationSeconds))
    $lines.Add(('Configuration:   ' + $(if ($UnsavedUi) { 'Unsaved UI controls' } else { 'Saved config (' + $ConfigFile + ')' })))
    $lines.Add(('Scheduled Task:  ' + (Get-TaskStatus).Text))
    $lines.Add(('Log Location:    ' + $LogFile))
    $lines.Add('----------------------------------------------------------------')
    if ($Stderr) {
        $lines.Add('STDERR:')
        $lines.Add($Stderr.Trim())
        $lines.Add('----------------------------------------------------------------')
    }
    $lines.Add('OUTPUT:')
    if ($Stdout) {
        $lines.Add($Stdout.Trim())
    } else {
        $lines.Add('(no output)')
    }
    $lines.Add('================================================================')
    return ($lines -join [Environment]::NewLine)
}

$script:InvokeTestSweep = {
    try {
        $testButton.Enabled = $false
        $testStatus.ForeColor = $Palette.Secondary
        $testStatus.Text = 'Sampling...'

        $configToUse = $ConfigFile
        $script:TestIsUnsaved = $false
        try {
            $currentControls = Get-ControlSettings
            $currentJson = $currentControls | ConvertTo-Json -Depth 10
            $savedJson = if ([IO.File]::Exists($ConfigFile)) { [IO.File]::ReadAllText($ConfigFile, [Text.Encoding]::UTF8) } else { '' }
            $isDifferent = $true
            if ($savedJson) {
                try {
                    $normSaved = Invoke-SettingsNormalizer -Path $ConfigFile
                    $tempVerify = Join-Path $env:TEMP ('saispin_chk_' + [Guid]::NewGuid().ToString('N') + '.json')
                    [IO.File]::WriteAllText($tempVerify, $currentJson, (New-Object Text.UTF8Encoding($false)))
                    $normCurrent = Invoke-SettingsNormalizer -Path $tempVerify
                    [IO.File]::Delete($tempVerify)
                    $s1 = $normSaved.settings | ConvertTo-Json -Depth 8
                    $s2 = $normCurrent.settings | ConvertTo-Json -Depth 8
                    $isDifferent = -not [string]::Equals($s1, $s2, [StringComparison]::Ordinal)
                } catch { $isDifferent = $true }
            }
            if ($isDifferent) {
                $script:TestIsUnsaved = $true
                $script:TestTempConfig = Join-Path $env:TEMP ('saispin_ui_testcfg_' + [Guid]::NewGuid().ToString('N') + '.json')
                [IO.File]::WriteAllText($script:TestTempConfig, $currentJson, (New-Object Text.UTF8Encoding($false)))
                $configToUse = $script:TestTempConfig
            }
        } catch { }

        $prefix = if ($script:TestIsUnsaved) { '[unsaved UI] ' } else { '' }
        $resultLabel.ForeColor = $Palette.Secondary
        $resultLabel.Text = $prefix + 'Sampling active processes (dry-run, no kills)...'

        $script:TestRunspace = [runspacefactory]::CreateRunspace()
        $script:TestRunspace.Open()
        $script:TestPs = [PowerShell]::Create()
        $script:TestPs.Runspace = $script:TestRunspace
        [void]$script:TestPs.AddScript({
            param($WatcherPath, $ConfigPath, $PowerShellExe)
            $output = & $PowerShellExe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $WatcherPath -TestSweep -ConfigFile $ConfigPath 2>&1
            return [pscustomobject]@{
                ExitCode = $LASTEXITCODE
                Output = ($output | ForEach-Object { "$_" }) -join "`n"
            }
        })
        [void]$script:TestPs.AddArgument($Watcher)
        [void]$script:TestPs.AddArgument($configToUse)
        [void]$script:TestPs.AddArgument($PowerShellExe)

        $script:TestStartTime = [datetime]::UtcNow
        $script:TestAsyncResult = $script:TestPs.BeginInvoke()

        $script:TestTimerTickHandler = {
            try {
                $elapsed = ([datetime]::UtcNow - $script:TestStartTime).TotalSeconds
                if ($script:TestAsyncResult -and $script:TestAsyncResult.IsCompleted) {
                    if ($script:TestTimer) { $script:TestTimer.Stop() }
                    $invokeResult = $script:TestPs.EndInvoke($script:TestAsyncResult)
                    $res = if ($invokeResult -and $invokeResult.Count -gt 0) { $invokeResult[0] } else { $null }
                    $exitCode = if ($res) { $res.ExitCode } else { -1 }
                    $rawOutput = if ($res) { [string]$res.Output } else { '' }

                    $prefix = if ($script:TestIsUnsaved) { '[unsaved UI] ' } else { '' }
                    $stdoutTrim = $rawOutput.Trim()

                    $matched = $exitCode -eq 0 -and $stdoutTrim -match 'TEST SWEEP: sampled=\d+ suspicious=\d+ alerts=\d+ kills=0'
                    $statusStr = if ($matched) { 'PASS (No kills; dry-run)' } else { 'FAIL' }
                    $script:LastDiagnostics = Format-DiagnosticsReport -Status $statusStr -ExitCode $exitCode `
                        -Stdout $rawOutput -Stderr '' -DurationSeconds $elapsed -UnsavedUi $script:TestIsUnsaved

                    if ($matched) {
                        $testStatus.ForeColor = $Palette.Highlight
                        $testStatus.Text = $prefix + 'No kills; dry-run'
                        $matchLine = @($stdoutTrim -split '\r?\n' | Where-Object { $_ -match 'TEST SWEEP:' })[0]
                        $resultLabel.ForeColor = $Palette.Text
                        $resultLabel.Text = $prefix + $(if ($matchLine) { $matchLine } else { @($stdoutTrim -split '\r?\n')[0] })
                    } else {
                        $testStatus.ForeColor = $Palette.Danger
                        $testStatus.Text = $prefix + 'Test failed'
                        $errLine = @($stdoutTrim -split '\r?\n' | Where-Object { $_.Trim() })[0]
                        $resultLabel.ForeColor = $Palette.Danger
                        $resultLabel.Text = $prefix + $(if ($errLine) { $errLine } else { 'Process exited with code ' + $exitCode })
                    }
                    Clean-TestSweepResources
                    $testButton.Enabled = $true
                } elseif ($elapsed -gt 45.0) {
                    if ($script:TestTimer) { $script:TestTimer.Stop() }
                    $prefix = if ($script:TestIsUnsaved) { '[unsaved UI] ' } else { '' }
                    $testStatus.ForeColor = $Palette.Danger
                    $testStatus.Text = $prefix + 'Timed out'
                    $resultLabel.ForeColor = $Palette.Danger
                    $resultLabel.Text = $prefix + 'Test sweep timed out after 45 seconds.'
                    $script:LastDiagnostics = Format-DiagnosticsReport -Status 'TIMED_OUT' -ExitCode -1 `
                        -Stdout '' -Stderr 'Process timed out after 45s and was cancelled.' -DurationSeconds $elapsed -UnsavedUi $script:TestIsUnsaved
                    Clean-TestSweepResources
                    $testButton.Enabled = $true
                }
            } catch {
                $testButton.Enabled = $true
                $testStatus.ForeColor = $Palette.Danger
                $testStatus.Text = 'Test failed'
                $resultLabel.ForeColor = $Palette.Danger
                $resultLabel.Text = $_.Exception.Message
                Clean-TestSweepResources
            }
        }

        $script:TestTimer = New-Object System.Windows.Forms.Timer
        $script:TestTimer.Interval = 200
        $script:TestTimer.add_Tick($script:TestTimerTickHandler)
        $script:TestTimer.Start()
    } catch {
        $testButton.Enabled = $true
        $testStatus.ForeColor = $Palette.Danger
        $testStatus.Text = 'Test failed'
        $resultLabel.ForeColor = $Palette.Danger
        $resultLabel.Text = $_.Exception.Message
        Clean-TestSweepResources
    }
}
$testButton.add_Click($script:InvokeTestSweep)

$script:InvokeCopyDiag = {
    try {
        $diagText = $script:LastDiagnostics
        if (-not $diagText) {
            $taskInfo = Get-TaskStatus
            $diagText = @(
                "================================================================"
                "SAISPIN SYSTEM & TASK DIAGNOSTICS"
                "================================================================"
                "Timestamp:       " + (Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz')
                "Task Status:     " + $taskInfo.Text
                "Status Code:     " + $taskInfo.StatusCode
                "Last Run Time:   " + $(if ($taskInfo.LastRunTime) { $taskInfo.LastRunTime } else { 'Never' })
                "Last Result:     " + $(if ($taskInfo.LastTaskResult -ne $null) { '0x' + $taskInfo.LastTaskResult.ToString('X') } else { 'None' })
                "Config File:     " + $ConfigFile
                "Log File:        " + $LogFile
                "Auto-Kill Mode:  " + $autoRadio.Checked
                "Sweep Cadence:   " + $intervalBox.Value + " min"
                "CPU Threshold:   " + $cpuBox.Value + "%"
                "Hot Hits:        " + $hitsBox.Value
                "Min Hot Minutes: " + $minutesBox.Value
                "================================================================"
            ) -join [Environment]::NewLine
        }
        Set-ClipboardSafe $diagText
        $resultLabel.ForeColor = $Palette.Highlight
        $resultLabel.Text = 'Diagnostics copied to clipboard.'
    } catch {
        $resultLabel.ForeColor = $Palette.Danger
        $resultLabel.Text = 'Failed to copy diagnostics: ' + $_.Exception.Message
    }
}
$copyDiagButton.add_Click($script:InvokeCopyDiag)

$openLogButton.add_Click({
    try {
        $target = if ([IO.File]::Exists($LogFile)) { $LogFile }
            elseif ([IO.File]::Exists((Join-Path $RepoRoot 'saispin.log'))) { Join-Path $RepoRoot 'saispin.log' }
            else { Split-Path -Parent $LogFile }
        if ([IO.File]::Exists($target)) {
            Start-Process notepad.exe -ArgumentList ('"' + $target + '"')
            $resultLabel.ForeColor = $Palette.Highlight
            $resultLabel.Text = 'Opened log: ' + (Split-Path -Leaf $target)
        } elseif (Test-Path -LiteralPath $target) {
            Start-Process explorer.exe -ArgumentList ('"' + $target + '"')
            $resultLabel.ForeColor = $Palette.Secondary
            $resultLabel.Text = 'Opened folder: ' + $target
        } else {
            $dir = Split-Path -Parent $LogFile
            if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            Start-Process explorer.exe -ArgumentList ('"' + $dir + '"')
            $resultLabel.ForeColor = $Palette.Secondary
            $resultLabel.Text = 'Opened folder: ' + $dir
        }
    } catch {
        $resultLabel.ForeColor = $Palette.Danger
        $resultLabel.Text = 'Failed to open log: ' + $_.Exception.Message
    }
})

$form.add_FormClosing({ Clean-TestSweepResources })

$saveButton.add_Click({
    $temporaryConfig = Join-Path (Split-Path -Parent $ConfigFile) ('.candidate-' + [Guid]::NewGuid().ToString('N') + '.json')
    $priorExists = [IO.File]::Exists($ConfigFile)
    $priorBytes = if ($priorExists) { [IO.File]::ReadAllBytes($ConfigFile) } else { $null }
    try {
        $settings = Get-ControlSettings
        $candidateText = $settings | ConvertTo-Json -Depth 10
        $candidateDirectory = Split-Path -Parent $ConfigFile
        if (-not (Test-Path -LiteralPath $candidateDirectory)) {
            New-Item -ItemType Directory -Path $candidateDirectory -Force | Out-Null
        }
        [IO.File]::WriteAllText($temporaryConfig, $candidateText, (New-Object System.Text.UTF8Encoding($false)))
        $checked = Invoke-SettingsNormalizer -Path $temporaryConfig
        if ($checked.warning) { throw ('Settings rejected: ' + $checked.warning) }
        $normalizedText = $checked.settings | ConvertTo-Json -Depth 10
        Write-AtomicText -Path $ConfigFile -Text $normalizedText

        $arguments = @(
            '-NoLogo', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass',
            '-File', $Installer, '-ConfigFile', $ConfigFile,
            '-IntervalMinutes', [string][int]$intervalBox.Value
        )
        if ($autoRadio.Checked) { $arguments += '-AutoKill' }
        $output = & $PowerShellExe @arguments 2>&1
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0) { throw ('Task update failed (exit ' + $exitCode + '): ' + (($output | ForEach-Object { "$_" }) -join ' ')) }
        $status = Get-TaskStatus
        $statusLabel.Text = $status.Text
        $statusLabel.ForeColor = if ($status.Text.StartsWith('CONFIG_TASK_MISMATCH')) { $Palette.Danger } else { $Palette.Secondary }
        $resultLabel.Text = 'Settings saved; scheduled task verified.'
        $resultLabel.ForeColor = $Palette.Highlight
        $script:modeAutoAtOpen = [bool]$status.AutoKill
        $script:modeArmConfirmed = $false
    } catch {
        $failureMessage = $_.Exception.Message
        $restoreFailed = $false
        try {
            if ($priorExists) { Write-AtomicBytes -Path $ConfigFile -Bytes $priorBytes }
            elseif ([IO.File]::Exists($ConfigFile)) { [IO.File]::Delete($ConfigFile) }
        } catch { $restoreFailed = $true }
        $taskRollbackFailed = $failureMessage -match '(?i)(restoring the previous task also failed|removing the partial task also failed)'
        if ($restoreFailed -or $taskRollbackFailed) {
            if ($restoreFailed -and $taskRollbackFailed) {
                $statusLabel.Text = 'CONFIG_TASK_MISMATCH: settings and task rollback failed'
            } elseif ($restoreFailed) {
                $statusLabel.Text = 'CONFIG_TASK_MISMATCH: settings rollback failed'
            } else {
                $statusLabel.Text = 'CONFIG_TASK_MISMATCH: task rollback failed'
            }
            $statusLabel.ForeColor = $Palette.Danger
        }
        $resultLabel.ForeColor = $Palette.Danger
        $resultLabel.Text = $failureMessage
    } finally {
        if ([IO.File]::Exists($temporaryConfig)) { [IO.File]::Delete($temporaryConfig) }
    }
})

$closeButton.add_Click({ $form.Close() })
$form.AcceptButton = $saveButton
$form.CancelButton = $closeButton
if ($SelfTestLayout) {
    $roundTripPath = Join-Path $env:TEMP ('saispin_ui_roundtrip_' + [Guid]::NewGuid().ToString('N') + '.json')
    $roundTripOk = $false
    try {
        $uiSettings = Get-ControlSettings | ConvertTo-Json -Depth 10
        Write-AtomicText -Path $roundTripPath -Text $uiSettings
        $uiPolicy = Invoke-SettingsNormalizer -Path $roundTripPath
        $roundTripOk = $null -eq $uiPolicy.warning -and
            $uiPolicy.settings.thresholds.cpu_percent -eq [int]$cpuBox.Value -and
            $uiPolicy.settings.allowlist -contains 'safe.exe' -and
            $uiPolicy.settings.process_rules.'worker.exe'.mode -eq 'alert_only'
    } finally {
        if ([IO.File]::Exists($roundTripPath)) { [IO.File]::Delete($roundTripPath) }
    }
    $layoutOk = $form.ClientSize.Width -eq 430 -and $form.ClientSize.Height -eq 400 -and
        $form.Font.FontFamily.Name -eq 'Verdana' -and $tabs.Width -le $form.ClientSize.Width - 20 -and
        $tabs.DrawMode -eq [System.Windows.Forms.TabDrawMode]::OwnerDrawFixed -and
        -not $policyTab.UseVisualStyleBackColor -and -not $processTab.UseVisualStyleBackColor -and
        $closeButton.Right -le $form.ClientSize.Width - 10 -and $resultLabel.Bottom -le $form.ClientSize.Height -and
        $roundTripOk
    if ($LayoutCapturePath) {
        $form.ShowInTaskbar = $false
        $form.Opacity = 0.0
        $form.Show()
        [System.Windows.Forms.Application]::DoEvents()
        $form.Refresh()
        $form.CreateControl()
        $form.PerformLayout()
        $bitmap = New-Object System.Drawing.Bitmap($form.Width, $form.Height)
        try {
            $form.DrawToBitmap($bitmap, (New-Object System.Drawing.Rectangle(0, 0, $form.Width, $form.Height)))
            $bitmap.Save($LayoutCapturePath, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $bitmap.Dispose()
            $form.Close()
        }
    }
    if ($layoutOk) { Write-Output 'SAISPIN_SETTINGS_LAYOUT: PASS'; exit 0 }
    Write-Output ('SAISPIN_SETTINGS_LAYOUT: FAIL size={0}x{1} font={2} draw={3} pageStyles={4}/{5} pageColors={6}/{7} closeRight={8} resultBottom={9} roundTrip={10}' -f
        $form.ClientSize.Width, $form.ClientSize.Height, $form.Font.FontFamily.Name, $tabs.DrawMode,
        $policyTab.UseVisualStyleBackColor, $processTab.UseVisualStyleBackColor,
        $policyTab.BackColor, $processTab.BackColor, $closeButton.Right, $resultLabel.Bottom, $roundTripOk)
    exit 1
}
if ($TestSweepUi) {
    $tempConfigCreated = $false
    if (-not [IO.File]::Exists($ConfigFile)) {
        $initialSettings = Get-ControlSettings | ConvertTo-Json -Depth 10
        Write-AtomicText -Path $ConfigFile -Text $initialSettings
        $tempConfigCreated = $true
    }

    $form.ShowInTaskbar = $false
    $form.Opacity = 0.0
    $form.Show()
    [System.Windows.Forms.Application]::DoEvents()

    # 1. Trigger Test Sweep with saved configuration
    & $script:InvokeTestSweep
    [System.Windows.Forms.Application]::DoEvents()

    $start = [datetime]::UtcNow
    while (-not $testButton.Enabled -and ([datetime]::UtcNow - $start).TotalSeconds -lt 25) {
        if ($script:TestAsyncResult -and $script:TestAsyncResult.IsCompleted) {
            & $script:TestTimerTickHandler
            break
        }
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 100
    }

    $sweepStatus = $testStatus.Text
    $sweepLabel = $resultLabel.Text
    $sweepOk = $testButton.Enabled -and $sweepStatus -eq 'No kills; dry-run' -and
        $sweepLabel -match 'TEST SWEEP: sampled=\d+ suspicious=\d+ alerts=\d+ kills=0'

    # 2. Test Copy Diag button
    & $script:InvokeCopyDiag
    [System.Windows.Forms.Application]::DoEvents()
    $copyLabel = $resultLabel.Text
    $copyOk = $copyLabel -eq 'Diagnostics copied to clipboard.' -and
        (-not [string]::IsNullOrEmpty($script:LastDiagnostics))

    # 3. Test unsaved UI detection
    $cpuBox.Value = [decimal]95
    & $script:InvokeTestSweep
    [System.Windows.Forms.Application]::DoEvents()

    $start = [datetime]::UtcNow
    while (-not $testButton.Enabled -and ([datetime]::UtcNow - $start).TotalSeconds -lt 25) {
        if ($script:TestAsyncResult -and $script:TestAsyncResult.IsCompleted) {
            & $script:TestTimerTickHandler
            break
        }
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 100
    }

    $unsavedStatus = $testStatus.Text
    $unsavedLabel = $resultLabel.Text
    $unsavedOk = $testButton.Enabled -and $unsavedStatus -eq '[unsaved UI] No kills; dry-run' -and
        $unsavedLabel -match '\[unsaved UI\] TEST SWEEP: sampled=\d+ suspicious=\d+ alerts=\d+ kills=0'

    $form.Close()
    if ($tempConfigCreated -and [IO.File]::Exists($ConfigFile)) {
        try { [IO.File]::Delete($ConfigFile) } catch { }
    }

    if ($sweepOk -and $copyOk -and $unsavedOk) {
        Write-Output 'SAISPIN_SETTINGS_SWEEP_UI: PASS'
        exit 0
    }
    Write-Output ('SAISPIN_SETTINGS_SWEEP_UI: FAIL sweepOk={0} copyOk={1} unsavedOk={2} sweepStatus="{3}" unsavedStatus="{4}" label="{5}"' -f
        $sweepOk, $copyOk, $unsavedOk, $sweepStatus, $unsavedStatus, $unsavedLabel)
    exit 1
}
[void]$form.ShowDialog()

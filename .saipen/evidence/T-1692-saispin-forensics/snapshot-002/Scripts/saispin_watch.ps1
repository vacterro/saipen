<#
.SYNOPSIS
    SAISPIN -- orphan CPU watchdog for SAITULS.

.DESCRIPTION
    One sweep: enumerate processes, sample accumulated CPU twice 3 seconds
    apart, decide who is an orphan, hand every observation to the pure decision
    engine in Scripts\saispin_logic.py, then notify, log and (only when
    explicitly enabled) terminate.

    The engine owns every rule that can end a process. This script owns the
    Windows half: enumeration, sampling, parent identity, atomic state,
    notification, the single-instance mutex and the kill re-validation.

    Default mode is DRY-RUN: nothing is terminated unless -AutoKill is passed.

.EXAMPLE
    .\Scripts\saispin_watch.ps1 -DryRun
    .\Scripts\saispin_watch.ps1 -AutoKill
    .\Scripts\saispin_watch.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    # Explicit dry-run. Also the default: -AutoKill is the only way to arm it.
    [switch]$DryRun,
    # Arm automatic termination. -DryRun wins if both are passed.
    [switch]$AutoKill,
    # Exercise the helpers and the engine wiring without sampling or notifying.
    [switch]$SelfTest,
    # Sample current processes without writing state, notifying, or killing.
    [switch]$TestSweep,
    [string]$ConfigFile,
    [string]$StateFile,
    [string]$LogFile,
    [string]$NotifyFile,
    [string]$EngineFile,
    [string]$PythonExe = 'python'
)

$ErrorActionPreference = 'Stop'

$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
$RepoRoot  = Split-Path -Parent $ScriptDir

$DataRoot = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { $env:TEMP }
$DataDir  = Join-Path $DataRoot 'SAITULS\SAISPIN'

if (-not $StateFile)  { $StateFile  = Join-Path $DataDir 'saispin_state.json' }
if (-not $LogFile)    { $LogFile    = Join-Path $DataDir 'saispin.log' }
if (-not $NotifyFile) { $NotifyFile = Join-Path $DataDir 'saispin_notify.json' }
if (-not $EngineFile) { $EngineFile = Join-Path $ScriptDir 'saispin_logic.py' }
if (-not $ConfigFile) { $ConfigFile = Join-Path $DataDir 'settings.json' }

# Recovery leases: the ONLY positive ownership token that can authorize a
# kill. Kept beside the other runtime data, overridable through the same
# environment variable the engine reads, so tests and the controlled-kill
# acceptance run fully isolated from the production tree.
$Script:LeaseDir = if ($env:SAISPIN_LEASE_DIR) { $env:SAISPIN_LEASE_DIR } else { Join-Path $DataDir 'leases' }
# The decision engine runs as a child process and resolves its own lease
# directory from this variable -- pin both sides to one path.
$env:SAISPIN_LEASE_DIR = $Script:LeaseDir

function Sync-LegacyDataFiles {
    param([string]$TargetDirectory, [string]$SourceDirectory)
    if (-not (Test-Path -LiteralPath $TargetDirectory)) {
        try { New-Item -ItemType Directory -Path $TargetDirectory -Force | Out-Null } catch { return }
    }
    $map = @{
        'saispin_state.json'  = $StateFile
        'saispin_notify.json' = $NotifyFile
        'saispin.log'         = $LogFile
    }
    foreach ($entry in $map.GetEnumerator()) {
        $sourcePath = Join-Path $SourceDirectory $entry.Key
        $targetPath = $entry.Value
        if ((Test-Path -LiteralPath $sourcePath) -and (-not (Test-Path -LiteralPath $targetPath))) {
            try {
                if ($entry.Key -like '*.json') {
                    $raw = [IO.File]::ReadAllText($sourcePath, [Text.Encoding]::UTF8)
                    if ($raw) { [void]($raw | ConvertFrom-Json) }
                }
                Copy-Item -LiteralPath $sourcePath -Destination $targetPath -Force
            } catch { }
        }
    }
}
if (-not $SelfTest -and -not $TestSweep) {
    $defaultStatePath = Join-Path $DataDir 'saispin_state.json'
    if ([string]::Equals([IO.Path]::GetFullPath($StateFile), [IO.Path]::GetFullPath($defaultStatePath), [StringComparison]::OrdinalIgnoreCase)) {
        Sync-LegacyDataFiles -TargetDirectory $DataDir -SourceDirectory $RepoRoot
    }
}

$MutexName = 'Global\SAITULS_SAISPIN_WATCH'

# The window between the two accumulated-CPU readings. Three seconds is long
# enough that a scheduler hiccup cannot fake 80% of a core and short enough
# that a five-minute task barely notices.
$Script:SampleSeconds = 3
$Script:Settings = @{
    schema_version = 1
    thresholds = @{ cpu_percent = 80.0; required_hits = 6; minimum_hot_minutes = 30 }
    timing = @{ sample_seconds = 3; sweep_interval_minutes = 5; stale_gap_minutes = 30 }
    notifications = @{ enabled = $true; reminder_minutes = 60 }
    allowlist = @()
    process_rules = @{}
}

# How long an already-delivered tray notification stays suppressed for the same
# process identity. The watcher sweeps every five minutes and a runaway can spin
# for hours, so an unbounded repeat is 12 identical balloons an hour and a
# bounded silence is none at all; one reminder an hour is the compromise. The
# structured log still records every single sweep.
$Script:NotifyReminderSeconds = 3600

# Config-extensible never-kill names. The engine holds the hard list; this only
# adds to it, and adding can never make something MORE killable.
$Script:Allowlist = @()

# A kill needs proven-good history. Set false when the state file had to be
# thrown away, which downgrades every KILL to an ALERT inside the engine.
$Script:HistoryTrusted = $true
# P1-1: whether the policy in force is the configured one or the built-in
# safe defaults (normalizer failed or warned). Reported by Test Sweep so a
# sweep against fallback policy never reads as a sweep of the real policy.
$Script:SettingsFallback = $false
$Script:LogMaxBytes = 1048576
# P1-1: exit code Test Sweep asks the entry point for. 0 = a usable sweep.
$Script:SweepExitCode = 0
$Script:LogGenerations = 3

function Add-SaispinAuditRecord {
    param([string]$Line)
    # Keep each record bounded; rotation retains active + three prior files.
    $limit = [int]($Script:LogMaxBytes / 8)
    if ($Line.Length -gt $limit) { $Line = $Line.Substring(0, $limit) + ' [truncated]' }
    $bytes = [Text.Encoding]::UTF8.GetBytes($Line + [Environment]::NewLine)
    if ([IO.File]::Exists($LogFile) -and (Get-Item -LiteralPath $LogFile).Length + $bytes.Length -gt $Script:LogMaxBytes) {
        # Rename only. An active pre-kill record can move to .1, never be
        # truncated in place. A failed rotation propagates before termination.
        $oldest = "$LogFile.$Script:LogGenerations"
        if ([IO.File]::Exists($oldest)) { [IO.File]::Delete($oldest) }
        for ($n = $Script:LogGenerations - 1; $n -ge 1; $n--) {
            if ([IO.File]::Exists("$LogFile.$n")) { [IO.File]::Move("$LogFile.$n", "$LogFile.$($n + 1)") }
        }
        [IO.File]::Move($LogFile, "$LogFile.1")
    }
    $stream = [IO.File]::Open($LogFile, 'Append', 'Write', 'Read')
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}

function Write-SaispinLog {
    param([string]$Text, [string]$Level = 'INFO', [switch]$Durable)
    if ($TestSweep) {
        if ($Level -eq 'WARN')  { Write-Warning $Text }
        if ($Level -eq 'ERROR') { Write-Error $Text -ErrorAction Continue }
        return
    }
    $line = '{0:yyyy-MM-ddTHH:mm:sszzz} | {1} | {2}' -f (Get-Date), $Level.ToUpper(), $Text
    try { Add-SaispinAuditRecord $line } catch {
        if ($Durable) { throw }
        Write-Warning ('audit write failed: ' + $_.Exception.Message)
    }
    if ($Level -eq 'WARN')  { Write-Warning $Text }
    if ($Level -eq 'ERROR') { Write-Error $Text -ErrorAction Continue }
}

# Every timestamp that crosses a boundary goes through here first.
#
# This is not tidiness. ConvertFrom-Json silently turns an ISO-8601 string into
# a [datetime], so a stamp that went out as "2026-09-03T12:20:31Z" comes back as
# an object that never string-compares equal to itself. Two failures follow, and
# both are invisible: the pre-kill identity re-check always mismatches (nothing
# is ever terminated), and the persisted hot streak never matches the next
# sweep's sample (six consecutive hot samples never accumulate). One normalizer,
# applied on every crossing, is the whole defence.
function Format-Stamp {
    param($Value)
    if ($null -eq $Value) { return '' }
    if ($Value -is [datetime]) { return $Value.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') }
    $text = ([string]$Value).Trim()
    if ([string]::IsNullOrWhiteSpace($text)) { return '' }
    try {
        $parsed = [datetime]::Parse($text, [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        return $parsed.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    } catch {
        return $text
    }
}

# CIM stamps are local time with an offset; the engine compares ISO-8601 UTC.
function ConvertFrom-CimDate {
    param($Value)
    return (Format-Stamp $Value)
}

# UserModeTime + KernelModeTime are 100-nanosecond ticks of accumulated CPU.
function Get-CpuSeconds {
    param($Process)
    try {
        $ticks = [double]$Process.UserModeTime + [double]$Process.KernelModeTime
        return $ticks / 1e7
    } catch { return $null }
}

# The share of ONE logical core the process burned during the window. A null
# reading or a negative delta is missing information, so it reads as 0.0 --
# never as a large number that could manufacture a hot sample.
function Get-CorePercent {
    param($Before, $After, [double]$Seconds = 3)
    if ($null -eq $Before -or $null -eq $After -or $Seconds -le 0) { return 0.0 }
    $delta = [double]$After - [double]$Before
    if ($delta -le 0) { return 0.0 }
    return [math]::Round(($delta / $Seconds) * 100.0, 1)
}

# Command lines are unbounded, balloon tips are not. The full text goes to the
# structured log; this is what the notification carries.
function Format-Cmdline {
    param([string]$Value, [int]$Limit = 200)
    if ([string]::IsNullOrWhiteSpace($Value)) { return '(no command line)' }
    $text = $Value.Trim() -replace '\s+', ' '
    if ($text.Length -le $Limit) { return $text }
    return $text.Substring(0, $Limit - 3) + '...'
}

function Format-HotDuration {
    param([int]$Seconds)
    if ($Seconds -ge 86400) { return ('{0:0.#}d' -f ($Seconds / 86400.0)) }
    if ($Seconds -ge 3600)  { return ('{0:0.#}h' -f ($Seconds / 3600.0)) }
    return ('{0}m' -f [int][math]::Round($Seconds / 60.0))
}

# ---------------------------------------------------------------- state file

function Read-SaispinState {
    if (-not (Test-Path -LiteralPath $StateFile)) { return @{} }
    try {
        $raw = Get-Content -LiteralPath $StateFile -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return @{} }
        $parsed = $raw | ConvertFrom-Json
        $table = @{}
        foreach ($entry in $parsed.PSObject.Properties) {
            $table[$entry.Name] = ConvertTo-HistoryEntry $entry.Value
        }
        return $table
    } catch {
        # A corrupt state file starts an empty history, logs, and continues --
        # and marks the history untrusted so no kill can come out of it.
        Write-SaispinLog -Level WARN -Text ('state unreadable, starting empty: ' + $_.Exception.Message)
        $Script:HistoryTrusted = $false
        return @{}
    }
}

# One streak record with every stamp back in canonical string form. The engine
# re-checks a record's own pid/start_time against its key before trusting it, so
# a stamp that came back from JSON as a [datetime] would fail that check and
# silently restart the streak at one hit on every single sweep -- meaning six
# consecutive hot samples could never accumulate and nothing would ever be
# detected. Normalizing on both crossings is what keeps the streak real.
function ConvertTo-HistoryEntry {
    param($Entry)
    if ($null -eq $Entry) { return $null }
    return [ordered]@{
        pid        = [int]$Entry.pid
        start_time = Format-Stamp $Entry.start_time
        first_hot  = Format-Stamp $Entry.first_hot
        last_hot   = Format-Stamp $Entry.last_hot
        hits       = [int]$Entry.hits
        name       = [string]$Entry.name
        cmdline    = [string]$Entry.cmdline
    }
}

# Write beside the target, then swap the whole file in one filesystem
# operation. Never Copy: Copy TRUNCATES the destination and streams into it,
# which is precisely the half-written file this is supposed to prevent -- and a
# truncated state file reads as a fresh history, silently resetting every streak
# on the machine.
#
# File.Replace is the atomic swap but it requires the destination to exist, so
# the very first run (and a run after somebody deleted the file) uses Move
# instead. Move onto a missing target is equally atomic; it just cannot
# overwrite.
function Save-JsonAtomic {
    param([string]$Path, $Table, [string]$Label)
    $temp = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    try {
        $json = if ($Table -and $Table.Count -gt 0) { $Table | ConvertTo-Json -Depth 6 } else { '{}' }
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        $bytes = $utf8.GetBytes($json)
        $stream = [IO.File]::Open($temp, 'CreateNew', 'Write', 'None')
        try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        if ([System.IO.File]::Exists($Path)) {
            # [NullString]::Value, not $null: PowerShell converts a plain $null
            # argument to "" and File.Replace rejects it as an illegal path.
            [System.IO.File]::Replace($temp, $Path, [NullString]::Value)
        } else {
            [System.IO.File]::Move($temp, $Path)
        }
    } catch {
        # A failed write leaves the PREVIOUS file intact, which is the safe
        # outcome: a stale streak can only delay a detection, never cause a kill,
        # and a stale notify record costs at most one duplicate balloon.
        try { Remove-Item -LiteralPath $temp -Force -ErrorAction SilentlyContinue } catch { }
        throw ($Label + ' write failed: ' + $_.Exception.Message)
    }
}

function Write-SaispinState {
    param($History)
    Save-JsonAtomic -Path $StateFile -Table $History -Label 'state'
}

# ------------------------------------------------------------ notify ledger

# When each process identity was last shown to the user, and what it was told.
# Separate from the streak history ON PURPOSE: this file exists only to stop
# duplicate balloons, so losing it must cost one extra notification and nothing
# else. It can never influence a kill, so a corrupt read needs no trust flag --
# it just starts empty.
function Read-NotifyState {
    if (-not (Test-Path -LiteralPath $NotifyFile)) { return @{} }
    try {
        $raw = Get-Content -LiteralPath $NotifyFile -Raw -Encoding UTF8
        if ([string]::IsNullOrWhiteSpace($raw)) { return @{} }
        $parsed = $raw | ConvertFrom-Json
        $table = @{}
        foreach ($entry in $parsed.PSObject.Properties) {
            $table[$entry.Name] = [ordered]@{
                last_notified = Format-Stamp $entry.Value.last_notified
                action        = [string]$entry.Value.action
            }
        }
        return $table
    } catch {
        Write-SaispinLog -Level WARN -Text ('notify ledger unreadable, starting empty: ' + $_.Exception.Message)
        return @{}
    }
}

function Write-NotifyState {
    param($Ledger)
    try { Save-JsonAtomic -Path $NotifyFile -Table $Ledger -Label 'notify ledger' }
    catch { Write-SaispinLog -Level WARN -Text $_.Exception.Message }
}

# Seconds between two canonical stamps. An unparseable stamp returns a very
# large gap, never 0: the failure mode of this function is "notify again", which
# costs a duplicate balloon, rather than "stay silent", which loses the alert.
function Get-StampGapSeconds {
    param([string]$From, [string]$To)
    if ([string]::IsNullOrWhiteSpace($From) -or [string]::IsNullOrWhiteSpace($To)) { return [int]::MaxValue }
    try {
        $a = [datetime]::Parse($From, [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        $b = [datetime]::Parse($To, [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        return [int]([math]::Abs(($b - $a).TotalSeconds))
    } catch {
        return [int]::MaxValue
    }
}

# Should this identity get a balloon this sweep? Never seen, or the verdict
# changed (an ALERT that became a KILL is news), or the reminder window has
# elapsed. Otherwise the log line alone carries the sweep.
function Test-NotifyDue {
    param($Ledger, [string]$Key, [string]$Action, [string]$Now)
    $prior = $Ledger[$Key]
    if (-not $prior) { return $true }
    if ($prior.action -ne $Action) { return $true }
    return ((Get-StampGapSeconds -From $prior.last_notified -To $Now) -ge $Script:NotifyReminderSeconds)
}

# The ledger entry to carry into the next sweep. When nothing was shown, the
# stamp of the last REAL notification is carried forward untouched -- stamping
# every sweep would restart the window every five minutes, so the hourly
# reminder would never come due and the second balloon would never arrive.
function New-NotifyRecord {
    param($Prior, [string]$Action, [string]$Now, [bool]$Notified)
    $stamp = if ($Notified -or -not $Prior) { $Now } else { [string]$Prior.last_notified }
    return [ordered]@{
        last_notified = $stamp
        action        = $Action
    }
}

# ------------------------------------------------------------ decision engine

function Invoke-SaispinEngine {
    param($History, $Samples, [bool]$ArmKill)

    if (-not (Test-Path -LiteralPath $EngineFile)) {
        throw "decision engine not found: $EngineFile"
    }
    $payload = [ordered]@{
        history         = if ($History) { $History } else { @{} }
        samples         = @($Samples)
        auto_kill       = [bool]$ArmKill
        allowlist       = @($Script:Allowlist)
        history_trusted = [bool]$Script:HistoryTrusted
        settings        = $Script:Settings
    } | ConvertTo-Json -Depth 6 -Compress

    # The engine reads one JSON sweep on stdin and answers on stdout. Piping
    # keeps it a plain child process: no temp files, no shell quoting of a
    # payload that contains arbitrary command lines.
    #
    # Both pipes must be UTF-8 explicitly. Windows PowerShell 5.1 defaults
    # $OutputEncoding to ASCII, which silently replaces every non-ASCII byte
    # with a question mark -- so a process whose name or path contains any
    # accented or Cyrillic character comes back mangled. That is not cosmetic:
    # the kill gate compares the decision's image name against the live one, and
    # a mangled name never matches, so such a process could be detected but never
    # acted on, and the log line would name a process that does not exist.
    #
    # $global: is load-bearing. A plain assignment inside a function creates a
    # function-LOCAL copy of the automatic variable, while the native-command
    # pipe reads the session one -- so the local form looks correct, changes
    # nothing, and the mangling survives. Verified both ways on 5.1.
    $savedOut = $global:OutputEncoding
    $savedConsole = [Console]::OutputEncoding
    $savedPyIo = $env:PYTHONIOENCODING
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    try {
        $global:OutputEncoding = $utf8NoBom
        try { [Console]::OutputEncoding = $utf8NoBom } catch { }
        $env:PYTHONIOENCODING = 'utf-8'
        $answer = $payload | & $PythonExe $EngineFile --sweep
        $engineExit = $LASTEXITCODE
    } finally {
        $global:OutputEncoding = $savedOut
        try { [Console]::OutputEncoding = $savedConsole } catch { }
        $env:PYTHONIOENCODING = $savedPyIo
    }
    if ($engineExit -ne 0) { throw "decision engine exited $engineExit" }
    $parsed = $answer | ConvertFrom-Json

    # Re-canonicalize every stamp ConvertFrom-Json helpfully turned into a
    # [datetime]. Without this the identity strings the engine returned no longer
    # equal the ones it was given, and every later comparison quietly fails.
    foreach ($decision in $parsed.decisions) {
        $decision.start_time = Format-Stamp $decision.start_time
    }
    return $parsed
}

# The persisted history, keys and all, with canonical stamps.
function ConvertTo-HistoryTable {
    param($History)
    $table = @{}
    if ($History) {
        foreach ($entry in $History.PSObject.Properties) {
            $table[$entry.Name] = ConvertTo-HistoryEntry $entry.Value
        }
    }
    return $table
}

# ------------------------------------------------------------- notification

# The same mechanism the toolkit's tray apps use: a WinForms NotifyIcon
# balloon. A balloon needs a message pump, so the icon lives just long enough
# for the shell to pick the notification up and is then disposed.
function Show-SaispinAlert {
    param([string]$Title, [string]$Text)
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    } catch {
        # No WinForms (Server Core, remote session): the log line is still
        # written, so the alert is never silently lost.
        Write-SaispinLog -Level WARN -Text 'tray notification unavailable; logged only'
        return
    }
    $icon = $null
    try {
        $icon = New-Object System.Windows.Forms.NotifyIcon
        $icon.Icon = [System.Drawing.SystemIcons]::Warning
        $icon.Visible = $true
        $icon.BalloonTipTitle = $Title
        $icon.BalloonTipText = $Text
        $icon.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Warning
        $icon.ShowBalloonTip(5000)
        # Pump briefly. Without this the process can exit before the shell has
        # read the notification and nothing appears at all.
        $deadline = (Get-Date).AddMilliseconds(1200)
        while ((Get-Date) -lt $deadline) {
            [System.Windows.Forms.Application]::DoEvents()
            Start-Sleep -Milliseconds 50
        }
    } catch {
        Write-SaispinLog -Level WARN -Text ('tray notification failed: ' + $_.Exception.Message)
    } finally {
        if ($icon) {
            try { $icon.Visible = $false } catch { }
            try { $icon.Dispose() } catch { }
        }
    }
}

function Write-DecisionLog {
    param($Decision, [string]$HotText, [string]$Cmd, [bool]$ArmKill, [bool]$Notified = $true,
          $KillAttempted = $null, $KillConfirmed = $null)
    $fields = @(
        ('PID=' + $Decision.pid)
        ('START=' + $Decision.start_time)
        $Decision.name
        ('CPU=' + $Decision.cpu_percent)
        ('HOT=' + $HotText)
        ('HITS=' + $Decision.hits)
        ('ORPHAN=' + $(if ($Decision.orphan) { '1' } else { '0' }))
        ('ACTION=' + $Decision.action)
        ('DRYRUN=' + $(if ($ArmKill) { '0' } else { '1' }))
        ('NOTIFIED=' + $(if ($Notified) { '1' } else { '0' }))
    )
    if ($null -ne $KillAttempted) {
        $fields += ('kill_attempted=' + $(if ($KillAttempted) { 'true' } else { 'false' }))
        $fields += ('kill_confirmed=' + $(if ($KillConfirmed) { 'true' } else { 'false' }))
    }
    $fields += $Cmd
    Write-SaispinLog -Text ($fields -join ' | ')
}

# ------------------------------------------------------- enumeration + orphan

# One CIM enumeration, indexed by PID. Every per-process probe is wrapped: a
# process that vanishes between enumeration and reading, or refuses access, is
# skipped rather than aborting the sweep.
function Get-ProcessTable {
    $table = @{}
    $rows = $null
    try {
        $rows = Get-CimInstance -ClassName Win32_Process -ErrorAction Stop
    } catch {
        Write-SaispinLog -Level ERROR -Text ('process enumeration failed: ' + $_.Exception.Message)
        return $table
    }
    foreach ($row in $rows) {
        try {
            # Not $pid: that is a PowerShell automatic variable holding THIS
            # process's id, and shadowing it has bitten this repo before.
            $procId = [int]$row.ProcessId
            $table[$procId] = [pscustomobject]@{
                Pid       = $procId
                ParentPid = [int]$row.ParentProcessId
                Name      = [string]$row.Name
                StartTime = ConvertFrom-CimDate $row.CreationDate
                Cmdline   = [string]$row.CommandLine
                Cpu       = Get-CpuSeconds $row
            }
        } catch {
            continue
        }
    }
    return $table
}

# Orphan detection with the PID-reuse guard the spec insists on: a live process
# holding the parent PID is only the real parent if it could actually have
# started this child. A "parent" that started AFTER its child is a stranger
# that inherited the number, so the child is an orphan.
#
# An unreadable start time on either side is missing information, and missing
# information must not become evidence of orphanhood -- so it reads as
# non-orphan, the conservative answer.
function Test-Orphan {
    param($Child, $Table)
    if (-not $Child) { return $false }
    if ($Child.ParentPid -le 0) { return $true }
    $parent = $Table[[int]$Child.ParentPid]
    if (-not $parent) { return $true }
    if ([string]::IsNullOrEmpty($parent.StartTime) -or [string]::IsNullOrEmpty($Child.StartTime)) {
        return $false
    }
    return ($parent.StartTime -gt $Child.StartTime)
}

# "Main process" of a guarded image = no live ancestor running the same image.
# VS Code's renderer and extension-host children are fair game; the one process
# that owns the window is not, and only the tree can tell them apart.
function Test-MainProcess {
    param($Child, $Table)
    if (-not $Child -or [string]::IsNullOrEmpty($Child.Name)) { return $false }
    $seen = @{}
    $cursor = $Child
    for ($hop = 0; $hop -lt 32; $hop++) {
        if ($cursor.ParentPid -le 0) { break }
        if ($seen[$cursor.Pid]) { break }
        $seen[$cursor.Pid] = $true
        $parent = $Table[[int]$cursor.ParentPid]
        if (-not $parent) { break }
        if ([string]::IsNullOrEmpty($parent.StartTime) -or [string]::IsNullOrEmpty($cursor.StartTime)) { break }
        if ($parent.StartTime -gt $cursor.StartTime) { break }   # reused PID, not an ancestor
        if ($parent.Name -eq $Child.Name) { return $false }
        $cursor = $parent
    }
    return $true
}

function Test-ActiveProtectedProcess {
    param($Proc)
    if (-not $Proc) { return $false }
    if ($Proc.Pid -eq $PID) { return $true }
    $name = [string]$Proc.Name.Trim().ToLower()
    $protectedNames = @(
        'pytest.exe', 'vstest.console.exe', 'testhost.exe',
        'csc.exe', 'vbc.exe', 'cl.exe', 'link.exe', 'msbuild.exe', 'rustc.exe', 'cargo.exe', 'go.exe', 'javac.exe',
        'antigravity.exe', 'agy.exe', 'claude.exe', 'opencode.exe',
        'obs64.exe', 'obs32.exe', 'obs.exe', 'ffmpeg.exe'
    )
    if ($protectedNames -contains $name) { return $true }

    $cmd = [string]$Proc.Cmdline
    if ($cmd) {
        if ($cmd -match '(?i)(^|\s|[/\\])(pytest(\.exe)?|unittest|vitest|jest|mocha)(\s|$)' -or
            $cmd -match '(?i)-m\s+(pytest|unittest)\b' -or
            $cmd -match '(?i)(^|\s)node(\.exe)?\s+.*--test\b' -or
            $cmd -match '(?i)(antigravity|claude|opencode)\b.*(worker|server|serve|daemon)') {
            return $true
        }
    }
    return $false
}

# ------------------------------------------------------------------- the kill

# The PowerShell twin of the engine's evaluate_recovery_lease(): a lease file
# bound to the exact identity (PID + creation time), explicitly authorized and
# unexpired as of $ObservedAt (live UTC at the kill gate). A missing, forged,
# expired or foreign lease is a refusal -- command lines never authorize.
function Get-RecoveryLeaseVerdict {
    param([int]$ProcId, [string]$StartTime, [string]$ObservedAt)
    $safeStart = $StartTime -replace '[:/]', '_'
    $path = Join-Path $Script:LeaseDir ($ProcId.ToString() + '_' + $safeStart + '.json')
    if (-not (Test-Path -LiteralPath $path)) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'no recovery lease for this identity -- ownership unknown' }
    }
    try {
        $lease = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease unreadable -- ownership cannot be proven' }
    }
    if ($null -eq $lease) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease malformed -- ownership cannot be proven' }
    }
    if ([int]$lease.pid -ne $ProcId -or (Format-Stamp $lease.start_time) -ne (Format-Stamp $StartTime)) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease identity mismatch -- lease belongs to another process' }
    }
    if ($lease.authorized -ne $true) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease not authorized -- destructive recovery denied' }
    }
    $expiryText = Format-Stamp $lease.expires_at
    if ([string]::IsNullOrWhiteSpace($expiryText)) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease expiry unreadable -- ownership cannot be proven' }
    }
    try {
        $parsedExpiry = [datetime]::Parse($expiryText, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind)
        $parsedObserved = [datetime]::Parse((Format-Stamp $ObservedAt), [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind)
    } catch {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease expiry unreadable -- ownership cannot be proven' }
    }
    if ($parsedObserved -ge $parsedExpiry) {
        return [pscustomobject]@{ Eligible = $false; Reason = 'recovery lease expired -- authorization no longer valid' }
    }
    return [pscustomobject]@{ Eligible = $true; Reason = '' }
}

# Nothing here trusts the decision that arrived: the engine decided on a sample
# that is now seconds old. Every precondition is re-read against the live
# system, and a silent Stop-Process is not accepted as proof of death.
function Invoke-ProvenKill {
    param($Decision, [bool]$StateCommitted = $false)
    $result = [pscustomobject]@{ Attempted = $false; Confirmed = $false; Refused = '' }
    $procId = [int]$Decision.pid

    # The engine already applied the allowlist, but this is the last gate before
    # a real termination and it costs one comparison. A decision object that was
    # replayed, hand-fed or produced by a future caller must not be the only
    # thing standing between Stop-Process and lsass.exe.
    if ($Decision.allowlisted -or $procId -le 4) {
        $result.Refused = 'never-kill process'
        return $result
    }

    $table = Get-ProcessTable
    $live = $table[$procId]
    if (-not $live) {
        $result.Refused = 'process already gone'
        return $result
    }
    if ($live.StartTime -ne $Decision.start_time) {
        # The PID was recycled between the decision and now. Killing it would
        # end an innocent process that merely inherited the number.
        $result.Refused = 'identity changed (PID reuse) since the decision'
        return $result
    }
    if ($live.Name -ne $Decision.name) {
        $result.Refused = 'image name changed since the decision'
        return $result
    }
    if (-not (Test-Orphan -Child $live -Table $table)) {
        $result.Refused = 'parent is alive again'
        return $result
    }
    if ($procId -eq $PID) {
        $result.Refused = 'watchdog self-process'
        return $result
    }
    if (Test-ActiveProtectedProcess -Proc $live) {
        $result.Refused = 'active protected work (test runner, compiler, or agent)'
        return $result
    }
    try {
        if (-not ([System.Management.Automation.PSTypeName]'SaispinNativeUser32').Type) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class SaispinNativeUser32 {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
}
'@ -ErrorAction SilentlyContinue
        }
        $fgWnd = [SaispinNativeUser32]::GetForegroundWindow()
        if ($fgWnd -ne [IntPtr]::Zero) {
            $fgPid = 0
            [SaispinNativeUser32]::GetWindowThreadProcessId($fgWnd, [ref]$fgPid) | Out-Null
            if ($fgPid -eq $procId) {
                $result.Refused = 'active user foreground window process'
                return $result
            }
        }
    } catch { }

    # Re-sample: the decision proved a sustained streak, this proves it is
    # STILL spinning right now rather than having gone quiet.
    Start-Sleep -Seconds $Script:SampleSeconds
    $after = (Get-ProcessTable)[$procId]
    if (-not $after -or $after.StartTime -ne $Decision.start_time) {
        $result.Refused = 'process changed while re-sampling'
        return $result
    }
    $cpu = Get-CorePercent -Before $live.Cpu -After $after.Cpu -Seconds $Script:SampleSeconds
    $targetThreshold = 80.0
    if ($Decision.PSObject.Properties['threshold_cpu'] -and $Decision.threshold_cpu) {
        $targetThreshold = [double]$Decision.threshold_cpu
    } elseif ($Script:Settings -and $Script:Settings.thresholds -and $Script:Settings.thresholds.cpu_percent) {
        $targetThreshold = [double]$Script:Settings.thresholds.cpu_percent
    }
    if ($Script:Settings -and $Script:Settings.process_rules) {
        $ruleKey = $live.Name.Trim().ToLower()
        if ($Script:Settings.process_rules.$ruleKey -and $Script:Settings.process_rules.$ruleKey.cpu_percent) {
            $targetThreshold = [double]$Script:Settings.process_rules.$ruleKey.cpu_percent
        }
    }
    if ($cpu -le $targetThreshold) {
        $result.Refused = ('no longer hot (' + $cpu + '% core, threshold ' + $targetThreshold + '%)')
        return $result
    }

    if (-not $StateCommitted) {
        $result.Refused = 'durable state unavailable'
        return $result
    }
    try {
        Write-SaispinLog -Durable -Text ('PRE-KILL | PID=' + $procId + ' | StartTime=' + $Decision.start_time + ' | state committed')
    } catch {
        $result.Refused = 'durable pre-kill audit unavailable: ' + $_.Exception.Message
        return $result
    }

    # Last gate before Stop-Process: re-read the recovery lease against the
    # live clock. Everything else above proves what the process IS; only the
    # lease proves somebody owns it and authorized destructive recovery. No
    # lease, no kill -- heuristic certainty is never enough (P0-1).
    $leaseVerdict = Get-RecoveryLeaseVerdict -ProcId $procId -StartTime $Decision.start_time `
        -ObservedAt ((Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))
    if (-not $leaseVerdict.Eligible) {
        $result.Refused = $leaseVerdict.Reason
        return $result
    }

    try {
        $result.Attempted = $true
        Stop-Process -Id $procId -Force -ErrorAction Stop
    } catch {
        $result.Refused = 'Stop-Process failed: ' + $_.Exception.Message
        return $result
    }

    Start-Sleep -Milliseconds 750
    $check = (Get-ProcessTable)[$procId]
    # Gone, or the PID is already somebody else: either way the process this
    # decision was about is dead. Same PID and same start time = it survived.
    $result.Confirmed = (-not $check) -or ($check.StartTime -ne $Decision.start_time)
    if (-not $result.Confirmed) { $result.Refused = 'process survived the kill' }
    return $result
}

# ------------------------------------------------------- sample construction

# The sweep's per-process records, built once from the two readings.
#
# A List, not `$samples += `: `+=` on a PowerShell array allocates a whole new
# array and copies every element already in it, so appending N records costs
# N^2/2 copies. Measured on this machine, that append is roughly a sixth of the
# construction cost at a few hundred processes -- the per-process helper calls
# below dominate it -- but it is the only part that grows with the SQUARE of the
# machine, so it is the part that gets worse on its own. Lifted out of
# Invoke-Sweep so the self-test can drive it with two synthetic tables and no CIM
# at all.
function New-SampleSet {
    param($Before, $After, [string]$ObservedAt, [double]$Seconds = 3)
    $samples = New-Object 'System.Collections.Generic.List[object]'
    foreach ($key in $After.Keys) {
        try {
            $now = $After[$key]
            $was = $Before[$key]
            # Only processes present in BOTH readings have a CPU delta. A
            # process born inside the window gets sampled on the next sweep.
            if (-not $was -or $was.StartTime -ne $now.StartTime) { continue }
            $samples.Add([ordered]@{
                pid             = $now.Pid
                start_time      = $now.StartTime
                name            = $now.Name
                cpu_percent     = Get-CorePercent -Before $was.Cpu -After $now.Cpu -Seconds $Seconds
                orphan          = [bool](Test-Orphan -Child $now -Table $After)
                observed_at     = $ObservedAt
                cmdline         = Format-Cmdline $now.Cmdline
                is_main_process = [bool](Test-MainProcess -Child $now -Table $After)
            })
        } catch {
            continue
        }
    }
    # One copy on the way out, not one per append. ToArray is deliberate: on
    # .NET 10 the `@(...)` wrapper Invoke-SaispinEngine puts around the samples
    # throws "Argument types do not match" when handed a List[object] straight,
    # so the sweep died on its first real payload while every synthetic test
    # passed. The comma then keeps the array whole instead of letting PowerShell
    # unroll it into the pipeline.
    return ,$samples.ToArray()
}

# One balloon per sweep, not one per process. The message pump inside
# Show-SaispinAlert costs 1.2 seconds, so N alerting processes used to cost
# N x 1.2s of sweep wall time AND N stacked balloons -- and the shell collapses
# a burst of notifications anyway, so most of that was paid for and thrown away.
#
# The shell caps balloon text, so a long list is trimmed with a count of what
# did not fit. Nothing is lost: saispin.log carries every alert in full whatever
# happens here.
function Format-AlertBatch {
    param($Lines, [bool]$ArmKill, [int]$Limit = 250)
    $all = @($Lines)
    $head = 'SAISPIN: ' + $all.Count + ' processes spinning (' +
        $(if ($ArmKill) { 'AUTO-KILL' } else { 'DRY-RUN' }) + ')'
    $body = New-Object 'System.Collections.Generic.List[string]'
    $body.Add($head)
    $body.Add('')
    $used = $head.Length + 2
    $shown = 0
    foreach ($line in $all) {
        $reserve = ('+' + ($all.Count - $shown) + ' more in saispin.log').Length + 2
        if (($used + $line.Length + 2 + $reserve) -gt $Limit) { break }
        $body.Add($line)
        $used += $line.Length + 2
        $shown++
    }
    if ($shown -lt $all.Count) {
        $body.Add('+' + ($all.Count - $shown) + ' more in saispin.log')
    }
    return ($body -join "`r`n")
}

# ------------------------------------------------------- structured sweep result

# P1-1: one machine-readable line for Test Sweep. The GUI parses THIS --
# status plus counts -- never a success-looking shape alone. Every distinct
# outcome the contract names gets its own status, so "nothing enumerated" can
# never present as "swept clean":
#   OK                    usable enumeration, valid sampling, zero kills
#   ENUMERATION_FAILED    Get-ProcessTable returned nothing
#   INCOMPLETE_SECOND_SAMPLE  the post-window reading was empty
#   NO_CPU_MEASUREMENTS   enumeration worked but no process survived both readings
#   ENGINE_FAILED         the decision engine threw or exited non-zero
# policy= is orthogonal: policy=fallback means the sweep ran on built-in safe
# defaults, not the configured policy -- reported, not fatal.
function Write-TestSweepResult {
    param([string]$Status, [int]$Sampled = 0, [int]$Hot = 0, [int]$Sustained = 0,
          [int]$Orphan = 0, [int]$Protected = 0, [int]$Eligible = 0, [int]$Rejected = 0,
          [int]$Alerts = 0, [int]$ExitCode = 0)
    $policy = if ($Script:SettingsFallback) { 'fallback' } else { 'ok' }
    Write-Output ('TEST SWEEP RESULT: status=' + $Status + ' policy=' + $policy +
        ' sampled=' + $Sampled + ' hot=' + $Hot + ' sustained=' + $Sustained +
        ' orphan=' + $Orphan + ' protected=' + $Protected + ' eligible=' + $Eligible +
        ' rejected=' + $Rejected + ' alerts=' + $Alerts + ' kills=0 (always zero in test sweep)')
    $Script:SweepExitCode = $ExitCode
}

# ------------------------------------------------------------------ one sweep

function Invoke-Sweep {
    param([bool]$ArmKill, [bool]$TestOnly = $false)

    $before = Get-ProcessTable
    if ($before.Count -eq 0) {
        if ($TestOnly) {
            # Unavailable data must never read as a successful safety check.
            Write-TestSweepResult -Status 'ENUMERATION_FAILED' -ExitCode 2
            return
        }
        $Script:SweepExitCode = 2
        Write-SaispinLog -Level WARN -Text 'sweep aborted: no processes could be enumerated'
        return
    }
    Start-Sleep -Seconds $Script:SampleSeconds
    $after = Get-ProcessTable
    if ($TestOnly -and $after.Count -eq 0) {
        Write-TestSweepResult -Status 'INCOMPLETE_SECOND_SAMPLE' -ExitCode 3
        return
    }
    $observedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')

    $samples = New-SampleSet -Before $before -After $after -ObservedAt $observedAt `
        -Seconds $Script:SampleSeconds

    if ($TestOnly -and $samples.Count -eq 0) {
        Write-TestSweepResult -Status 'NO_CPU_MEASUREMENTS' -ExitCode 4
        return
    }

    $history = Read-SaispinState
    if ($TestOnly) {
        # Engine failure is a first-class outcome, not a crash the GUI has to
        # scrape: it gets its own status and a failing exit code.
        try {
            $answer = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill $false
        } catch {
            Write-TestSweepResult -Status 'ENGINE_FAILED' -ExitCode 5
            Write-Output ('TEST SWEEP ENGINE ERROR: ' + $_.Exception.Message)
            return
        }
    } else {
        $answer = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill ($ArmKill -and -not $TestOnly)
    }
    if ($TestOnly) {
        $suspicious = @($answer.decisions | Where-Object { $_.hot }).Count
        $alertsOnly = @($answer.decisions | Where-Object { $_.action -eq 'ALERT' }).Count
        $orphanedCount = @($samples | Where-Object { $_.orphan }).Count
        $sustainedCount = @($answer.decisions | Where-Object { $_.sustained }).Count
        $protectedCount = @($answer.decisions | Where-Object { $_.allowlisted }).Count
        $eligibleCount = @($answer.decisions | Where-Object { $_.action -eq 'KILL' }).Count
        $rejectedCount = @($answer.decisions | Where-Object { $_.hot -and $_.action -ne 'KILL' }).Count
        Write-TestSweepResult -Status 'OK' -Sampled $samples.Count -Hot $suspicious `
            -Sustained $sustainedCount -Orphan $orphanedCount -Protected $protectedCount `
            -Eligible $eligibleCount -Rejected $rejectedCount -Alerts $alertsOnly -ExitCode 0
        foreach ($d in ($answer.decisions | Where-Object { $_.hot -or $_.action -ne 'IGNORE' } | Select-Object -First 10)) {
            Write-Output ('  PID {0} ({1}): {2}% core, orphan={3}, classification={4}, reason={5}' -f
                $d.pid, $d.name, $d.cpu_percent, $d.orphan, $d.classification, $d.reason)
        }
        return
    }

    # Persist first. A kill must never be the only durable record of a sweep,
    # and the next run's streak must survive a crash inside the alert path.
    $nextHistory = ConvertTo-HistoryTable $answer.history
    $stateCommitted = $false
    try { Write-SaispinState -History $nextHistory; $stateCommitted = $true }
    catch { Write-SaispinLog -Level WARN -Text ('KILL REFUSED: durable state unavailable; ALERT only: ' + $_.Exception.Message) }

    # The ledger is rebuilt from the identities seen THIS sweep, so a process
    # that died drops out and a returning PID starts fresh -- no pruning pass
    # and no file that grows for the life of the machine.
    $notifyEnabled = [bool]$Script:Settings.notifications.enabled
    $ledger = if ($notifyEnabled) { Read-NotifyState } else { @{} }
    $nextLedger = @{}

    # Every balloon this sweep owes, delivered once at the end.
    $pending = New-Object 'System.Collections.Generic.List[object]'

    $alerts = 0
    $killed = 0
    foreach ($decision in $answer.decisions) {
        if ($decision.action -eq 'IGNORE') { continue }
        $alerts++
        $hot = Format-HotDuration -Seconds ([int]$decision.hot_seconds)
        $cmd = Format-Cmdline $decision.cmdline
        $orphanText = if ($decision.orphan) { 'YES' } else { 'NO' }
        $key = [string]$decision.pid + ':' + $decision.start_time

        if ($decision.action -eq 'KILL') {
            $kill = if ($stateCommitted) { Invoke-ProvenKill -Decision $decision -StateCommitted $true }
                else { [pscustomobject]@{ Attempted = $false; Confirmed = $false; Refused = 'durable state unavailable; ALERT only' } }
            if ($kill.Confirmed) { $killed++ }
            $verb = if ($kill.Confirmed) { 'KILLED' } elseif ($kill.Attempted) { 'KILL FAILED' } else { 'KILL REFUSED' }
            # The verb, not the action, is what the user is being told: a refusal
            # that later becomes a real kill is new information and must break
            # through the reminder window.
            $due = $notifyEnabled -and (Test-NotifyDue -Ledger $ledger -Key $key -Action $verb -Now $observedAt)
            if ($due) {
                $pending.Add([pscustomobject]@{
                    Detail = @(
                        'SAISPIN: orphan spin ' + $verb.ToLower()
                        ''
                        'PID: ' + $decision.pid
                        'Process: ' + $decision.name
                        'CPU: ' + $decision.cpu_percent + '% core'
                        'Duration: ' + $hot
                        'Orphan: ' + $orphanText
                        'Action: ' + $verb
                        'Command: ' + $cmd
                    ) -join "`r`n"
                    Line = ('{0} {1} {2}% core {3} {4}' -f $decision.pid, $decision.name,
                        $decision.cpu_percent, $hot, $verb)
                })
            }
            $nextLedger[$key] = New-NotifyRecord -Prior $ledger[$key] -Action $verb -Now $observedAt -Notified $due
            Write-DecisionLog -Decision $decision -HotText $hot -Cmd $cmd -ArmKill $ArmKill -Notified $due `
                -KillAttempted $kill.Attempted -KillConfirmed $kill.Confirmed
            if ($kill.Refused) {
                Write-SaispinLog -Text ('PID=' + $decision.pid + ' | kill not completed: ' + $kill.Refused)
            }
            continue
        }

        $due = $notifyEnabled -and (Test-NotifyDue -Ledger $ledger -Key $key -Action 'ALERT' -Now $observedAt)
        if ($due) {
            $pending.Add([pscustomobject]@{
                Detail = @(
                    'SAISPIN: sustained CPU process detected'
                    ''
                    'PID: ' + $decision.pid
                    'Process: ' + $decision.name
                    'CPU: ' + $decision.cpu_percent + '% core'
                    'Duration: ' + $hot
                    'Orphan: ' + $orphanText
                    'Mode: ' + $(if ($ArmKill) { 'AUTO-KILL' } else { 'DRY-RUN' })
                    'Command: ' + $cmd
                ) -join "`r`n"
                Line = ('{0} {1} {2}% core {3}{4}' -f $decision.pid, $decision.name,
                    $decision.cpu_percent, $hot, $(if ($decision.orphan) { ' orphan' } else { '' }))
            })
        }
        $nextLedger[$key] = New-NotifyRecord -Prior $ledger[$key] -Action 'ALERT' -Now $observedAt -Notified $due
        Write-DecisionLog -Decision $decision -HotText $hot -Cmd $cmd -ArmKill $ArmKill -Notified $due
    }

    # A single process keeps the full detail it always had; several share one
    # balloon, because the second 1.2-second pump in a row is a second the sweep
    # spends achieving nothing.
    if ($pending.Count -eq 1) {
        Show-SaispinAlert -Title 'SAISPIN' -Text $pending[0].Detail
    } elseif ($pending.Count -gt 1) {
        Show-SaispinAlert -Title 'SAISPIN' `
            -Text (Format-AlertBatch -Lines @($pending | ForEach-Object { $_.Line }) -ArmKill $ArmKill)
    }

    if ($notifyEnabled) { Write-NotifyState -Ledger $nextLedger }

    Write-SaispinLog -Text ('sweep complete: ' + $samples.Count + ' processes sampled, ' +
        $alerts + ' alert(s), ' + $pending.Count + ' notified, ' + $killed + ' kill(s), mode=' +
        $(if ($ArmKill) { 'auto-kill' } else { 'dry-run' }))
}

# ------------------------------------------------------------------ self-test

# Proves the Windows-side helpers and the engine wiring on synthetic data: no
# sampling window, no notification, no termination. A build can check the
# watcher this way, because a real sweep needs a real runaway to be interesting.
function Invoke-SelfTest {
    $script:selfTestFailures = 0

    $pct = Get-CorePercent -Before 100.0 -After 102.9 -Seconds 3
    Confirm-That 'a 2.9s CPU delta over a 3s window reads as ~97% of one core' `
        ($pct -gt 96 -and $pct -lt 97) ("$pct")
    Confirm-That 'a negative delta reads as 0%, never a huge number' `
        ((Get-CorePercent -Before 500 -After 10 -Seconds 3) -eq 0.0) 'PID reuse mid-sweep'
    Confirm-That 'an unreadable CPU counter reads as 0%' `
        ((Get-CorePercent -Before $null -After 10 -Seconds 3) -eq 0.0) 'missing info is not a hot sample'

    $long = ('x' * 400)
    Confirm-That 'the command line is trimmed for the balloon' `
        ((Format-Cmdline $long).Length -eq 200) ((Format-Cmdline $long).Length.ToString() + ' chars')
    Confirm-That 'an empty command line is labelled, not blank' `
        ((Format-Cmdline '') -eq '(no command line)') (Format-Cmdline '')
    Confirm-That 'hot duration renders in m/h' `
        ((Format-HotDuration 2100) -eq '35m' -and (Format-HotDuration 7200) -eq '2h') `
        ((Format-HotDuration 2100) + ' / ' + (Format-HotDuration 7200))

    Test-OrphanRules
    Test-SampleConstruction
    Test-StateRoundTrip
    Test-NotifyPolicy
    Test-KillGuards
    Test-DurableKillAndRotation
    Test-EngineWiring

    Write-Output '---'
    if ($script:selfTestFailures -eq 0) { Write-Output 'PASS (0 failures)' }
    else { Write-Output ('FAILED (' + $script:selfTestFailures + ' failures)') }
}

function Confirm-That {
    param([string]$Name, [bool]$Ok, [string]$Detail = '')
    if ($Ok) {
        Write-Output ('PASS  ' + $Name + $(if ($Detail) { '  -> ' + $Detail } else { '' }))
    } else {
        $script:selfTestFailures++
        Write-Output ('FAIL  ' + $Name + '  -> ' + $Detail)
    }
}

# Drop a recovery lease fixture for one identity inside $Script:LeaseDir.
# Callers that need isolation must Set-Variable LeaseDir first and restore it.
function New-LeaseFixture {
    param([int]$ProcId, [string]$StartTime, [bool]$Authorized = $true,
          [string]$Expires = '2099-01-01T00:00:00Z', [string]$AsJson = $null)
    if (-not (Test-Path -LiteralPath $Script:LeaseDir)) {
        New-Item -ItemType Directory -Path $Script:LeaseDir -Force | Out-Null
    }
    $safeStart = $StartTime -replace '[:/]', '_'
    $path = Join-Path $Script:LeaseDir ($ProcId.ToString() + '_' + $safeStart + '.json')
    $body = if ($AsJson) { $AsJson } else {
        (@{ pid = $ProcId; start_time = $StartTime; authorized = $Authorized; expires_at = $Expires } |
            ConvertTo-Json -Compress)
    }
    [IO.File]::WriteAllText($path, $body, (New-Object System.Text.UTF8Encoding($false)))
    return $path
}

function New-FakeProcess {
    param([int]$Id, [int]$Parent, [string]$Name, [string]$Start,
          [double]$Cpu = 1.0, [string]$Cmdline = '')
    return [pscustomobject]@{
        Pid = $Id; ParentPid = $Parent; Name = $Name
        StartTime = $Start; Cmdline = $Cmdline; Cpu = $Cpu
    }
}

function Test-OrphanRules {
    # A synthetic tree: 200 is a live child of 100; 300's parent PID 999 was
    # reused by a process that started LATER than its supposed child; 400's
    # parent is simply gone; 501 is a code.exe child of a code.exe root.
    $t = @{}
    $t[100] = New-FakeProcess 100 1   'bash.exe'   '2026-09-03T10:00:00Z'
    $t[200] = New-FakeProcess 200 100 'python.exe' '2026-09-03T11:00:00Z'
    $t[300] = New-FakeProcess 300 999 'python.exe' '2026-09-03T11:00:00Z'
    $t[999] = New-FakeProcess 999 1   'chrome.exe' '2026-09-03T12:00:00Z'
    $t[400] = New-FakeProcess 400 555 'python.exe' '2026-09-03T11:00:00Z'
    $t[500] = New-FakeProcess 500 100 'code.exe'   '2026-09-03T11:00:00Z'
    $t[501] = New-FakeProcess 501 500 'code.exe'   '2026-09-03T11:05:00Z'

    Confirm-That 'a live parent means not orphaned' `
        (-not (Test-Orphan -Child $t[200] -Table $t)) 'PID 200 under a live bash'
    Confirm-That 'a missing parent means orphaned' `
        (Test-Orphan -Child $t[400] -Table $t) 'parent PID 555 is gone'
    Confirm-That 'a parent PID reused by a NEWER process is still an orphan' `
        (Test-Orphan -Child $t[300] -Table $t) 'PID 999 started after its child'
    Confirm-That 'an unreadable start time is NOT read as orphanhood' `
        (-not (Test-Orphan -Child (New-FakeProcess 601 100 'x.exe' '') -Table $t)) `
        'missing evidence is not evidence'
    Confirm-That 'the root of a guarded image is the main process' `
        (Test-MainProcess -Child $t[500] -Table $t) 'no code.exe ancestor'
    Confirm-That 'a code.exe child is not the main process' `
        (-not (Test-MainProcess -Child $t[501] -Table $t)) 'its parent is code.exe too'
}

# Two synthetic readings of a machine carrying $Count processes, all under one
# live root, the second reading 3 CPU-seconds richer than the first. No CIM, so
# the sample construction can be measured at sizes this box will never reach.
function New-FakeReadings {
    param([int]$Count)
    $before = @{}
    $after = @{}
    $before[1] = New-FakeProcess 1 0 'root.exe' '2026-09-03T09:00:00Z' 0.0
    $after[1]  = New-FakeProcess 1 0 'root.exe' '2026-09-03T09:00:00Z' 0.0
    for ($i = 0; $i -lt $Count; $i++) {
        $procId = 1000 + $i
        $before[$procId] = New-FakeProcess $procId 1 'worker.exe' '2026-09-03T10:00:00Z' 100.0 'worker --job'
        $after[$procId]  = New-FakeProcess $procId 1 'worker.exe' '2026-09-03T10:00:00Z' 102.9 'worker --job'
    }
    return @{ Before = $before; After = $after }
}

# Sample construction: the record shape must not move, and the cost must track
# the number of processes rather than its square. `$samples += ` copied the whole
# array on every append, so a 600-process machine paid ~180000 element copies to
# look for one runaway.
function Test-SampleConstruction {
    $before = @{}
    $after = @{}
    # Present in both readings and burning a core: the one record expected out.
    $before[200] = New-FakeProcess 200 1 'python.exe' '2026-09-03T11:00:00Z' 100.0 'python  spin.py'
    $after[200]  = New-FakeProcess 200 1 'python.exe' '2026-09-03T11:00:00Z' 102.9 'python  spin.py'
    # Same PID, different identity between the readings: a recycled number.
    $before[300] = New-FakeProcess 300 1 'a.exe' '2026-09-03T11:00:00Z' 10.0
    $after[300]  = New-FakeProcess 300 1 'b.exe' '2026-09-03T11:30:00Z' 10.0
    # Born inside the window: no delta to measure, sampled next sweep.
    $after[400]  = New-FakeProcess 400 1 'new.exe' '2026-09-03T11:29:00Z' 5.0

    $set = New-SampleSet -Before $before -After $after -ObservedAt '2026-09-03T11:30:00Z' -Seconds 3
    Confirm-That 'only processes present in both readings are sampled' `
        ($set.Count -eq 1 -and $set[0].pid -eq 200) ('records=' + $set.Count)

    $shape = @($set[0].Keys)
    $expected = @('pid', 'start_time', 'name', 'cpu_percent', 'orphan', 'observed_at',
        'cmdline', 'is_main_process')
    Confirm-That 'the record keeps the exact eight keys in order' `
        (-not (Compare-Object $shape $expected -SyncWindow 0)) ($shape -join ',')

    $one = $set[0]
    Confirm-That 'every field carries the value the engine contract expects' `
        ($one.start_time -eq '2026-09-03T11:00:00Z' -and $one.name -eq 'python.exe' -and
         $one.cpu_percent -gt 96 -and $one.cpu_percent -lt 97 -and $one.orphan -eq $true -and
         $one.observed_at -eq '2026-09-03T11:30:00Z' -and $one.cmdline -eq 'python spin.py' -and
         $one.is_main_process -eq $true) `
        ('cpu=' + $one.cpu_percent + ' orphan=' + $one.orphan + ' cmd=' + $one.cmdline)

    # 10 -> 10000 processes. Reported as much as asserted: what this proves is
    # that construction stays inside a flat per-record cost at ten thousand
    # processes, sixteen times more than this machine actually carries.
    #
    # It is deliberately NOT the discrimination test for the fix. Measured, the
    # quadratic append costs ~0.03ms per record at 10000 against ~0.15ms of
    # per-record helper calls, so the bound below passes against the pre-fix
    # shape too -- a timing assertion cannot see a 20% difference through JIT
    # warmup and a busy machine. The static assertion after it is what actually
    # fails if the append comes back.
    $perRecord = @{}
    foreach ($size in 10, 100, 1000, 10000) {
        $readings = New-FakeReadings -Count $size
        $clock = [Diagnostics.Stopwatch]::StartNew()
        $built = New-SampleSet -Before $readings.Before -After $readings.After `
            -ObservedAt '2026-09-03T11:30:00Z' -Seconds 3
        $clock.Stop()
        # The live root is present in both readings too, so it is sampled with
        # the workers: $size workers plus one parent.
        Confirm-That ('sample construction handles ' + $size + ' processes') `
            ($built.Count -eq ($size + 1)) ('records=' + $built.Count + ' in ' + $clock.ElapsedMilliseconds + 'ms')
        $perRecord[$size] = [math]::Max($clock.Elapsed.TotalMilliseconds, 0.001) / ($size + 1)
    }
    $growth = $perRecord[10000] / $perRecord[1000]
    Confirm-That 'the per-process cost does not grow with the size of the machine' `
        ($growth -lt 4.0) ('10000 costs ' + [math]::Round($growth, 2) + 'x per record vs 1000')

    # The real gate on the fix: the append itself. A regression here is one
    # character wide and a timing test sleeps straight through it.
    $src = (Get-Command New-SampleSet).Definition
    Confirm-That 'the sample collection is appended to, never rebuilt per record' `
        ($src -match '\$samples\.Add\(' -and $src -notmatch '\$samples\s*\+=') `
        'List.Add, no array += in the loop'

    # The sample set must survive the trip into the engine EXACTLY as the sweep
    # builds it. Handing the engine a hand-built array instead is what let a
    # sweep-killing bug through once already: on .NET 10 the engine's `@(...)`
    # wrapper throws "Argument types do not match" on a List, so every synthetic
    # test passed while the first real sweep died.
    $probe = @{}
    $probeAfter = @{}
    $probe[900] = New-FakeProcess 900 1 'python.exe' '2026-09-03T11:00:00Z' 100.0 'python spin.py'
    $probeAfter[900] = New-FakeProcess 900 1 'python.exe' '2026-09-03T11:00:00Z' 102.9 'python spin.py'
    $live = New-SampleSet -Before $probe -After $probeAfter -ObservedAt '2026-09-03T11:30:00Z' -Seconds 3
    $answered = $null
    try {
        $answered = Invoke-SaispinEngine -History @{} -Samples $live -ArmKill $false
    } catch {
        Confirm-That 'the engine accepts the sample set the sweep actually builds' $false $_.Exception.Message
    }
    if ($answered) {
        Confirm-That 'the engine accepts the sample set the sweep actually builds' `
            ($answered.decisions.Count -eq 1 -and [int]$answered.decisions[0].pid -eq 900) `
            ('decisions=' + $answered.decisions.Count)
    }
}

# The state file is the only thing carrying a streak between two five-minute
# runs, so a stamp that does not survive the round trip means the streak silently
# restarts at one hit forever and nothing is ever detected. This writes a real
# file and reads it back rather than asserting on the formatter alone.
function Test-StateRoundTrip {
    $probe = Join-Path ([System.IO.Path]::GetTempPath()) ('saispin_state_' + [guid]::NewGuid().ToString('N') + '.json')
    $probeLog = $probe + '.log'
    $original = $StateFile
    $originalLog = $LogFile
    try {
        Set-Variable -Name StateFile -Scope Script -Value $probe
        # The self-test must not leave lines in the real watcher log: the corrupt
        # state case below is a deliberate warning, not an incident.
        Set-Variable -Name LogFile -Scope Script -Value $probeLog
        $entry = ConvertTo-HistoryEntry ([pscustomobject]@{
            pid = 30976; start_time = '2026-09-03T12:20:31Z'
            first_hot = '2026-09-03T14:00:00Z'; last_hot = '2026-09-03T14:24:00Z'
            hits = 5; name = 'python.exe'; cmdline = 'python ... tests/test_app.py'
        })
        Write-SaispinState -History @{ '30976:2026-09-03T12:20:31Z' = $entry }
        Confirm-That 'the state file is written' (Test-Path -LiteralPath $probe) $probe
        Confirm-That 'the first write leaves no .tmp behind' `
            (-not (Test-Path -LiteralPath ($probe + '.tmp'))) 'Move onto a missing target'

        $back = Read-SaispinState
        $one = $back['30976:2026-09-03T12:20:31Z']
        Confirm-That 'a persisted streak survives the JSON round trip as strings' `
            ($one -and $one.start_time -eq '2026-09-03T12:20:31Z' -and
             $one.first_hot -eq '2026-09-03T14:00:00Z' -and $one.hits -eq 5) `
            ('start_time=' + $one.start_time + ' hits=' + $one.hits)

        # The engine re-checks a record against its key before trusting it. If
        # the round trip broke the stamp, this sweep restarts at one hit.
        $sample = [ordered]@{ pid = 30976; start_time = '2026-09-03T12:20:31Z'
            name = 'python.exe'; cpu_percent = 97.0; orphan = $true
            observed_at = '2026-09-03T14:30:00Z'; cmdline = 'x'; is_main_process = $false }
        $answer = Invoke-SaispinEngine -History $back -Samples @($sample) -ArmKill $false
        Confirm-That 'the reloaded streak continues instead of restarting' `
            ($answer.decisions[0].hits -eq 6) ('hits=' + $answer.decisions[0].hits)

        # Overwrite the existing state file: the atomic-swap path, which is the
        # one that actually runs every five minutes forever. Copy-then-truncate
        # would pass a happy-path check like this too, so what is asserted is
        # that the swap left no debris and the NEW content is what reads back.
        Write-SaispinState -History (ConvertTo-HistoryTable $answer.history)
        $rewritten = Read-SaispinState
        Confirm-That 'overwriting an existing state file swaps it cleanly' `
            ($rewritten['30976:2026-09-03T12:20:31Z'].hits -eq 6 -and
             -not (Test-Path -LiteralPath ($probe + '.tmp'))) `
            ('hits=' + $rewritten['30976:2026-09-03T12:20:31Z'].hits)

        '{ this is not json' | Set-Content -LiteralPath $probe -Encoding UTF8
        $Script:HistoryTrusted = $true
        # The warning this read emits is the point of the case, not a problem
        # with it, so it stays out of the self-test transcript.
        $savedWarning = $WarningPreference
        $WarningPreference = 'SilentlyContinue'
        try { $broken = Read-SaispinState } finally { $WarningPreference = $savedWarning }
        Confirm-That 'a corrupt state file yields an empty, untrusted history' `
            ($broken.Count -eq 0 -and -not $Script:HistoryTrusted) `
            ('entries=' + $broken.Count + ' trusted=' + $Script:HistoryTrusted)
    } finally {
        $Script:HistoryTrusted = $true
        Set-Variable -Name StateFile -Scope Script -Value $original
        Set-Variable -Name LogFile -Scope Script -Value $originalLog
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath ($probe + '.tmp') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $probeLog -Force -ErrorAction SilentlyContinue
    }
}

# The notify ledger decides whether the user is told, so a bug here is either 12
# identical balloons an hour or total silence about a real runaway. Both branches
# are asserted, and the file itself is round-tripped: ConvertFrom-Json turns an
# ISO stamp into a [datetime], which would make every gap comparison throw and
# silently pick one of the two failure modes.
function Test-NotifyPolicy {
    $probe = Join-Path ([System.IO.Path]::GetTempPath()) ('saispin_notify_' + [guid]::NewGuid().ToString('N') + '.json')
    $probeLog = $probe + '.log'
    $original = $NotifyFile
    $originalLog = $LogFile
    $key = '30976:2026-09-03T12:20:31Z'
    try {
        Set-Variable -Name NotifyFile -Scope Script -Value $probe
        Set-Variable -Name LogFile -Scope Script -Value $probeLog

        Confirm-That 'an identity never notified before is due' `
            (Test-NotifyDue -Ledger @{} -Key $key -Action 'ALERT' -Now '2026-09-03T14:30:00Z') `
            'empty ledger'

        $ledger = @{ $key = (New-NotifyRecord -Prior $null -Action 'ALERT' -Now '2026-09-03T14:30:00Z' -Notified $true) }
        Confirm-That 'the same verdict inside the reminder window is suppressed' `
            (-not (Test-NotifyDue -Ledger $ledger -Key $key -Action 'ALERT' -Now '2026-09-03T14:35:00Z')) `
            '5 minutes later, no second balloon'
        Confirm-That 'the same verdict past the reminder window notifies again' `
            (Test-NotifyDue -Ledger $ledger -Key $key -Action 'ALERT' -Now '2026-09-03T15:30:00Z') `
            'one hour later'
        Confirm-That 'an escalated verdict breaks through the window' `
            (Test-NotifyDue -Ledger $ledger -Key $key -Action 'KILLED' -Now '2026-09-03T14:35:00Z') `
            'ALERT became KILLED'

        # The three kill outcomes are three different pieces of news. A refusal
        # that turned into a real attempt, and an attempt that finally landed,
        # both have to reach the user inside the quiet window.
        $refused = @{ $key = (New-NotifyRecord -Prior $null -Action 'KILL REFUSED' -Now '2026-09-03T14:30:00Z' -Notified $true) }
        Confirm-That 'a refused kill that became a failed attempt notifies immediately' `
            (Test-NotifyDue -Ledger $refused -Key $key -Action 'KILL FAILED' -Now '2026-09-03T14:35:00Z') `
            'KILL REFUSED became KILL FAILED'
        $failed = @{ $key = (New-NotifyRecord -Prior $null -Action 'KILL FAILED' -Now '2026-09-03T14:30:00Z' -Notified $true) }
        Confirm-That 'a failed kill that finally landed notifies immediately' `
            (Test-NotifyDue -Ledger $failed -Key $key -Action 'KILLED' -Now '2026-09-03T14:35:00Z') `
            'KILL FAILED became KILLED'
        Confirm-That 'an unreadable stamp errs toward notifying, not silence' `
            (Test-NotifyDue -Ledger @{ $key = @{ last_notified = 'garbage'; action = 'ALERT' } } `
                -Key $key -Action 'ALERT' -Now '2026-09-03T14:35:00Z') `
            'a lost alert is worse than a duplicate'

        # A suppressed sweep must not push the window forward, or the reminder
        # never comes due: every sweep would sit five minutes from the last stamp.
        $carried = New-NotifyRecord -Prior $ledger[$key] -Action 'ALERT' -Now '2026-09-03T14:35:00Z' -Notified $false
        Confirm-That 'a suppressed sweep keeps the original notification stamp' `
            ($carried.last_notified -eq '2026-09-03T14:30:00Z') ('stamp=' + $carried.last_notified)
        Confirm-That 'the reminder still comes due after repeated suppressed sweeps' `
            (Test-NotifyDue -Ledger @{ $key = $carried } -Key $key -Action 'ALERT' -Now '2026-09-03T15:30:00Z') `
            'window measured from the last real balloon'

        Write-NotifyState -Ledger $ledger
        Confirm-That 'the notify ledger is written with no .tmp left behind' `
            ((Test-Path -LiteralPath $probe) -and -not (Test-Path -LiteralPath ($probe + '.tmp'))) $probe
        $back = Read-NotifyState
        Confirm-That 'the ledger survives the JSON round trip as strings' `
            ($back[$key].last_notified -eq '2026-09-03T14:30:00Z' -and $back[$key].action -eq 'ALERT') `
            ('last_notified=' + $back[$key].last_notified)
        Confirm-That 'the reloaded ledger still suppresses inside the window' `
            (-not (Test-NotifyDue -Ledger $back -Key $key -Action 'ALERT' -Now '2026-09-03T14:35:00Z')) `
            'no duplicate after a restart'

        '{ not json at all' | Set-Content -LiteralPath $probe -Encoding UTF8
        $savedWarning = $WarningPreference
        $WarningPreference = 'SilentlyContinue'
        try { $broken = Read-NotifyState } finally { $WarningPreference = $savedWarning }
        Confirm-That 'a corrupt ledger starts empty and costs one extra balloon' `
            ($broken.Count -eq 0 -and (Test-NotifyDue -Ledger $broken -Key $key -Action 'ALERT' -Now '2026-09-03T14:35:00Z')) `
            ('entries=' + $broken.Count)

        # Twelve consecutive unchanged sweeps, five minutes apart: the runaway is
        # still there and every sweep must record it, but the user is told once.
        # This is the shape of a real afternoon -- before the ledger it was twelve
        # balloons and fourteen wasted seconds of pump.
        $sim = @{}
        $sweeps = 0
        $balloons = 0
        $start = [datetime]::Parse('2026-09-03T14:00:00Z', [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind)
        for ($i = 0; $i -lt 12; $i++) {
            $now = Format-Stamp $start.AddMinutes(5 * $i)
            $due = Test-NotifyDue -Ledger $sim -Key $key -Action 'ALERT' -Now $now
            if ($due) { $balloons++ }
            $sim[$key] = New-NotifyRecord -Prior $sim[$key] -Action 'ALERT' -Now $now -Notified $due
            $sweeps++
        }
        Confirm-That 'twelve unchanged sweeps log twelve decisions and show one balloon' `
            ($sweeps -eq 12 -and $balloons -eq 1) ('sweeps=' + $sweeps + ' balloons=' + $balloons)
        Confirm-That 'the thirteenth sweep, an hour after the first, shows the reminder' `
            (Test-NotifyDue -Ledger $sim -Key $key -Action 'ALERT' -Now (Format-Stamp $start.AddMinutes(60))) `
            'one reminder per hour, not per sweep'
        # Same identity, cold in between: the ledger is rebuilt from the sweep, so
        # a process that stopped spinning and started again is news once more.
        Confirm-That 'a cold-to-hot recurrence notifies immediately' `
            (Test-NotifyDue -Ledger @{} -Key $key -Action 'ALERT' -Now (Format-Stamp $start.AddMinutes(20))) `
            'an IGNORE sweep drops the identity from the ledger'
        # A recycled PID is a different identity, because the key carries the
        # start time -- so the new process is never silenced by the old one.
        Confirm-That 'a reused PID is a new identity and notifies immediately' `
            (Test-NotifyDue -Ledger $sim -Key '30976:2026-09-03T14:40:00Z' -Action 'ALERT' `
                -Now (Format-Stamp $start.AddMinutes(45))) 'same PID, later start time'

        # Several processes crossing the threshold in one sweep share one balloon.
        # The pump inside Show-SaispinAlert costs 1.2 seconds, so this is the
        # difference between one and N seconds of sweep time.
        $lines = 1..8 | ForEach-Object { ('{0} worker{0}.exe 99% core 35m orphan' -f (3000 + $_)) }
        $batch = Format-AlertBatch -Lines $lines -ArmKill $false
        Confirm-That 'a multi-process sweep produces one balloon naming the count and mode' `
            ($batch -like 'SAISPIN: 8 processes spinning (DRY-RUN)*') ($batch -split "`r`n")[0]
        Confirm-That 'the batch body stays inside the balloon text budget' `
            ($batch.Length -le 250) ($batch.Length.ToString() + ' chars')
        Confirm-That 'what did not fit is counted, not dropped silently' `
            ($batch -like '*more in saispin.log*') ($batch -split "`r`n")[-1]

        # Structural, because no harness can observe Invoke-Sweep without CIM: the
        # notification must not be reachable from inside the per-decision loop, or
        # the 1.2-second pump is back to costing 1.2 seconds per hot process.
        $src = (Get-Command Invoke-Sweep).Definition
        $loopAt = $src.IndexOf('foreach ($decision in $answer.decisions)')
        $deliverAt = $src.IndexOf('if ($pending.Count -eq 1)')
        $inLoop = if ($loopAt -ge 0 -and $deliverAt -gt $loopAt) {
            $src.Substring($loopAt, $deliverAt - $loopAt)
        } else { 'MARKERS NOT FOUND' }
        Confirm-That 'the sweep never notifies from inside the per-decision loop' `
            ($inLoop -ne 'MARKERS NOT FOUND' -and $inLoop -notmatch 'Show-SaispinAlert') `
            'one pump per sweep, whatever the process count'
    } finally {
        Set-Variable -Name NotifyFile -Scope Script -Value $original
        Set-Variable -Name LogFile -Scope Script -Value $originalLog
        Remove-Item -LiteralPath $probe -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath ($probe + '.tmp') -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $probeLog -Force -ErrorAction SilentlyContinue
    }
}

# The kill gate, exercised on decisions that must all be REFUSED. Every case
# here terminates nothing by design: a real process is never involved, because
# the point is proving the refusals fire before Stop-Process is reached.
function Test-DurableKillAndRotation {
    $dir = Join-Path ([IO.Path]::GetTempPath()) ('saispin-durability-' + [Guid]::NewGuid().ToString('N'))
    $oldState = $StateFile; $oldLog = $LogFile; $oldNotify = $NotifyFile
    $oldMax = $Script:LogMaxBytes
    $oldLeaseDir = $Script:LeaseDir
    $Script:LeaseDir = Join-Path $dir 'leases'
    $env:SAISPIN_LEASE_DIR = $Script:LeaseDir
    $script:durabilityStops = 0; $script:durabilityTick = 0; $script:durabilityGone = $false
    $decision = [pscustomobject]@{ pid = 424242; start_time = '2026-09-03T12:20:31Z'; name = 'fixture.exe'
        action = 'KILL'; allowlisted = $false; orphan = $true; cpu_percent = 100; hits = 6; hot_seconds = 1800; cmdline = 'fixture' }
    # Only process/notification boundaries are mocked. State, audit, rotation,
    # sweep ordering and the kill gate are the actual production functions.
    function Get-ProcessTable {
        if ($script:durabilityGone) { return @{} }
        $script:durabilityTick++
        return @{ 424242 = [pscustomobject]@{ Pid = 424242; ParentPid = 0; Name = 'fixture.exe'
            StartTime = '2026-09-03T12:20:31Z'; Cpu = 10 * $script:durabilityTick; Cmdline = 'fixture' } }
    }
    function Start-Sleep { param($Seconds, $Milliseconds) }
    function Stop-Process {
        param($Id, [switch]$Force, $ErrorAction)
        if ($Id -ne 424242) { throw 'unexpected test process identity' }
        $script:durabilityStops++; $script:durabilityGone = $true
    }
    function Show-SaispinAlert { param($Title, $Text) }
    function Invoke-SaispinEngine { param($History, $Samples, $ArmKill); return [pscustomobject]@{ history = [pscustomobject]@{}; decisions = @($decision) } }
    try {
        [void][IO.Directory]::CreateDirectory($dir)
        Set-Variable StateFile -Scope Script -Value (Join-Path $dir 'state.json')
        # Positive control: fixture identity 424242 holds a valid lease; the
        # refusal cases below still fire on their own earlier gates.
        [void](New-LeaseFixture -ProcId 424242 -StartTime '2026-09-03T12:20:31Z')
        Set-Variable LogFile -Scope Script -Value (Join-Path $dir 'saispin.log')
        Set-Variable NotifyFile -Scope Script -Value (Join-Path $dir 'notify.json')
        Write-SaispinState @{}
        $originalHash = (Get-FileHash -LiteralPath $StateFile -Algorithm SHA256).Hash
        $hold = [IO.File]::Open($StateFile, 'Open', 'Read', 'Read')
        try {
            $threw = $false
            try { Write-SaispinState @{ changed = $true } } catch { $threw = $true }
            Confirm-That 'state persistence failure throws to the caller' $threw 'locked state file'
            Invoke-Sweep -ArmKill $true
        } finally { $hold.Dispose() }
        Confirm-That 'failed durable state prevents termination in the actual sweep' ($script:durabilityStops -eq 0) 'KILL REFUSED / ALERT only'
        Confirm-That 'failed state write preserves prior bytes' ((Get-FileHash -LiteralPath $StateFile -Algorithm SHA256).Hash -eq $originalHash) 'atomic replacement'
        Confirm-That 'state refusal appears in audit log' ((Get-Content -Raw -LiteralPath $LogFile) -match 'KILL REFUSED: durable state unavailable') 'refusal is visible'

        $hold = [IO.File]::Open($LogFile, 'Open', 'Read', 'None')
        try { $refused = Invoke-ProvenKill -Decision $decision -StateCommitted $true } finally { $hold.Dispose() }
        Confirm-That 'unwritable pre-kill audit refuses termination' (-not $refused.Attempted -and $script:durabilityStops -eq 0 -and $refused.Refused -match 'audit unavailable') $refused.Refused

        $Script:LogMaxBytes = 1024
        for ($n = 0; $n -lt 80; $n++) { Write-SaispinLog -Durable -Text ('bounded old record ' + $n + ('x' * 60)) }
        $activeHash = (Get-FileHash -LiteralPath $LogFile -Algorithm SHA256).Hash
        # Fill active to just below cap, then prove rename preserves those bytes.
        [IO.File]::WriteAllText($LogFile, ('a' * 1000))
        $activeHash = (Get-FileHash -LiteralPath $LogFile -Algorithm SHA256).Hash
        Write-SaispinLog -Durable -Text 'PRE-KILL fixture rotation witness'
        Confirm-That 'rotation renames the active log byte-exact' ((Get-FileHash -LiteralPath ($LogFile + '.1') -Algorithm SHA256).Hash -eq $activeHash) 'no active-file truncation'
        $passed = Invoke-ProvenKill -Decision $decision -StateCommitted $true
        Write-SaispinLog -Durable -Text 'KILLED fixture outcome'
        Confirm-That 'committed state and audit reach mocked termination once' ($passed.Confirmed -and $script:durabilityStops -eq 1) 'positive control; no real process terminated'
        $logs = @(Get-ChildItem -LiteralPath $dir -Filter 'saispin.log*' -File)
        $retained = ($logs | ForEach-Object { [IO.File]::ReadAllText($_.FullName) }) -join ''
        Confirm-That 'newest pre-kill and outcome records survive rotation' ($retained -match 'PRE-KILL' -and $retained -match 'KILLED fixture outcome') 'retained records'
        Confirm-That 'log retention bounds generations and total bytes' ($logs.Count -le 4 -and ($logs | Measure-Object Length -Sum).Sum -le 4096) 'active plus three generations, 1024 bytes each'

        # P0-1 at the kill gate itself: the same decision, every earlier gate
        # satisfiable, but the recovery lease withdrawn -- Stop-Process must
        # stay unreachable and the refusal must name the missing ownership.
        $script:durabilityGone = $false
        Remove-Item -LiteralPath (Join-Path $Script:LeaseDir ('424242_2026-09-03T12_20_31Z.json')) -Force -ErrorAction SilentlyContinue
        $noLease = Invoke-ProvenKill -Decision $decision -StateCommitted $true
        Confirm-That 'the kill gate itself refuses without a recovery lease' `
            (-not $noLease.Attempted -and $noLease.Refused -like '*no recovery lease*' -and $script:durabilityStops -eq 1) `
            $noLease.Refused
        $script:durabilityGone = $false
        [IO.File]::WriteAllText($LogFile, ('b' * 1000))
        $hold = [IO.File]::Open($LogFile, 'Open', 'Read', 'None')
        try { $refused = Invoke-ProvenKill -Decision $decision -StateCommitted $true } finally { $hold.Dispose() }
        Confirm-That 'rotation failure refuses kill without truncating active log' (-not $refused.Attempted -and $script:durabilityStops -eq 1 -and (Get-Item -LiteralPath $LogFile).Length -eq 1000) 'rename blocked by locked active file'
    } finally {
        Set-Variable StateFile -Scope Script -Value $oldState
        Set-Variable LogFile -Scope Script -Value $oldLog
        Set-Variable NotifyFile -Scope Script -Value $oldNotify
        $Script:LogMaxBytes = $oldMax
        $Script:LeaseDir = $oldLeaseDir
        $env:SAISPIN_LEASE_DIR = $oldLeaseDir
        if ([IO.Directory]::Exists($dir)) { Remove-Item -LiteralPath $dir -Recurse -Force }
    }
}

function Test-KillGuards {
    $base = [pscustomobject]@{
        pid = 999999; start_time = '2026-09-03T12:20:31Z'; name = 'python.exe'
        action = 'KILL'; allowlisted = $false; orphan = $true
        cpu_percent = 99.0; hits = 6; hot_seconds = 1800; cmdline = 'x'
    }

    $allowlisted = $base.PSObject.Copy()
    $allowlisted.allowlisted = $true
    $verdict = Invoke-ProvenKill -Decision $allowlisted
    Confirm-That 'an allowlisted decision is refused at the kill gate itself' `
        (-not $verdict.Attempted -and $verdict.Refused -eq 'never-kill process') $verdict.Refused

    $kernel = $base.PSObject.Copy()
    $kernel.pid = 4
    $verdict = Invoke-ProvenKill -Decision $kernel
    Confirm-That 'PID 4 is refused at the kill gate even if a decision says KILL' `
        (-not $verdict.Attempted -and $verdict.Refused -eq 'never-kill process') $verdict.Refused

    # A PID that cannot exist: the gate must refuse on absence, not throw.
    $verdict = Invoke-ProvenKill -Decision $base
    Confirm-That 'a vanished process is refused, not chased' `
        (-not $verdict.Attempted -and $verdict.Refused -eq 'process already gone') $verdict.Refused

    # This very PowerShell process: alive, but its identity does not match the
    # decision, which is exactly the PID-reuse case.
    $mismatch = $base.PSObject.Copy()
    $mismatch.pid = $PID
    $verdict = Invoke-ProvenKill -Decision $mismatch
    Confirm-That 'a live process whose identity does not match is refused' `
        (-not $verdict.Attempted -and $verdict.Refused -like '*identity changed*') $verdict.Refused

    # Same process, correct start time, wrong image name.
    $selfNow = (Get-ProcessTable)[$PID]
    $renamed = $base.PSObject.Copy()
    $renamed.pid = $PID
    $renamed.start_time = $selfNow.StartTime
    $renamed.name = 'not-the-real-name.exe'
    $verdict = Invoke-ProvenKill -Decision $renamed
    Confirm-That 'a matching PID with a different image name is refused' `
        (-not $verdict.Attempted -and $verdict.Refused -like '*image name changed*') $verdict.Refused

    # Same process, right identity, but it has a live parent: the orphan gate
    # is the last thing standing, and it must hold. (This shell was started by
    # the test runner, so it genuinely has one.)
    $parented = $base.PSObject.Copy()
    $parented.pid = $PID
    $parented.start_time = $selfNow.StartTime
    $parented.name = $selfNow.Name
    $verdict = Invoke-ProvenKill -Decision $parented
    Confirm-That 'a process with a live parent is refused at the kill gate' `
        (-not $verdict.Attempted -and $verdict.Refused -eq 'parent is alive again') $verdict.Refused
}

function Test-EngineWiring {    # The real engine, on the two real incidents plus the counterexample, with
    # auto-kill ARMED and a history already carrying five hot samples over
    # half an hour -- so this sweep is the sixth and the gates are satisfiable.
    $history = @{
        '30976:2026-09-03T12:20:31Z' = @{
            pid = 30976; start_time = '2026-09-03T12:20:31Z'
            first_hot = '2026-09-03T14:00:00Z'; last_hot = '2026-09-03T14:24:00Z'
            hits = 5; name = 'python.exe'; cmdline = 'python ... tests/test_app.py'
        }
        '7777:2026-09-03T09:00:00Z' = @{
            pid = 7777; start_time = '2026-09-03T09:00:00Z'
            first_hot = '2026-09-03T14:00:00Z'; last_hot = '2026-09-03T14:24:00Z'
            hits = 5; name = 'csrss.exe'; cmdline = 'csrss'
        }
        '5100:2026-09-01T08:00:00Z' = @{
            pid = 5100; start_time = '2026-09-01T08:00:00Z'
            first_hot = '2026-09-03T14:00:00Z'; last_hot = '2026-09-03T14:24:00Z'
            hits = 5; name = 'cline.exe'; cmdline = 'cline --pathname /hub'
        }
    }
    $observed = '2026-09-03T14:30:00Z'
    $samples = @(
        [ordered]@{ pid = 30976; start_time = '2026-09-03T12:20:31Z'; name = 'python.exe'
            cpu_percent = 97.0; orphan = $true; observed_at = $observed
            cmdline = 'python ... tests/test_app.py'; is_main_process = $false }
        [ordered]@{ pid = 3116; start_time = '2026-09-03T10:00:00Z'; name = 'pytest.exe'
            cpu_percent = 0.3; orphan = $true; observed_at = $observed
            cmdline = 'pytest'; is_main_process = $false }
        [ordered]@{ pid = 7777; start_time = '2026-09-03T09:00:00Z'; name = 'csrss.exe'
            cpu_percent = 99.0; orphan = $true; observed_at = $observed
            cmdline = 'csrss'; is_main_process = $true }
        [ordered]@{ pid = 5100; start_time = '2026-09-01T08:00:00Z'; name = 'cline.exe'
            cpu_percent = 99.5; orphan = $false; observed_at = $observed
            cmdline = 'cline --pathname /hub'; is_main_process = $true }
    )

    # The engine resolves leases through SAISPIN_LEASE_DIR; isolate it so the
    # positive KILL expectation below proves lease-gated eligibility without
    # touching the real runtime tree.
    $oldLeaseDir = $Script:LeaseDir
    $leaseProbe = Join-Path ([IO.Path]::GetTempPath()) ('saispin_lease_' + [Guid]::NewGuid().ToString('N'))
    $Script:LeaseDir = $leaseProbe
    $env:SAISPIN_LEASE_DIR = $leaseProbe
    [void](New-LeaseFixture -ProcId 30976 -StartTime '2026-09-03T12:20:31Z')

    $answer = $null
    try {
        $answer = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill $true
    } catch {
        Confirm-That 'the decision engine answers a sweep' $false $_.Exception.Message
        $Script:LeaseDir = $oldLeaseDir
        $env:SAISPIN_LEASE_DIR = $oldLeaseDir
        return
    }
    Confirm-That 'the decision engine answers a sweep' `
        ($answer -and $answer.decisions.Count -eq 4) ('decisions=' + $answer.decisions.Count)

    $byPid = @{}
    foreach ($d in $answer.decisions) { $byPid[[int]$d.pid] = $d }

    Confirm-That 'the orphaned python worker is killed with auto-kill armed' `
        ($byPid[30976].action -eq 'KILL') ('action=' + $byPid[30976].action)
    Confirm-That 'the sleeping orphaned pytest is ignored' `
        ($byPid[3116].action -eq 'IGNORE') ('action=' + $byPid[3116].action)
    Confirm-That 'an allowlisted orphan spin alerts but is never killed' `
        ($byPid[7777].action -eq 'ALERT') ('action=' + $byPid[7777].action)
    Confirm-That 'a spinning process with a live parent alerts but is never killed' `
        ($byPid[5100].action -eq 'ALERT') ('action=' + $byPid[5100].action)
    Confirm-That 'the cold process is dropped from the persisted history' `
        (-not $answer.history.PSObject.Properties['3116:2026-09-03T10:00:00Z']) `
        'a sleeping orphan is not tracked'
    Confirm-That 'the log line carries the identity, the numbers and the verdict' `
        ($byPid[30976].start_time -eq '2026-09-03T12:20:31Z' -and
         $byPid[30976].hits -eq 6 -and $byPid[30976].hot_seconds -ge 1800) `
        ('hits=' + $byPid[30976].hits + ' hot=' + $byPid[30976].hot_seconds + 's')

    # Same sweep, auto-kill NOT armed: the exact same evidence must alert only.
    $dry = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill $false
    $dryKills = @($dry.decisions | Where-Object { $_.action -eq 'KILL' })
    Confirm-That 'without auto-kill the identical evidence kills nothing' `
        ($dryKills.Count -eq 0) ('KILL decisions=' + $dryKills.Count)

    # P0-1: identical evidence with the lease withdrawn. The counterexample
    # from the report -- python.exe, orphan, 97% core, six hot observations,
    # auto-kill armed -- must now stop at ALERT because ownership is unknown.
    Remove-Item -LiteralPath (Join-Path $leaseProbe ('30976_2026-09-03T12_20_31Z.json')) -Force -ErrorAction SilentlyContinue
    $noLease = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill $true
    $noLeaseByPid = @{}
    foreach ($d in $noLease.decisions) { $noLeaseByPid[[int]$d.pid] = $d }
    Confirm-That 'the policy counterexample no longer yields KILL without a lease' `
        ($noLeaseByPid[30976].action -eq 'ALERT' -and $noLeaseByPid[30976].reason -like '*no recovery lease*') `
        ('action=' + $noLeaseByPid[30976].action + ' reason=' + $noLeaseByPid[30976].reason)
    Confirm-That 'the unproven verdict is classified suspected stall, not recoverable' `
        ($noLeaseByPid[30976].classification -eq 'SUSPECTED_STALL') `
        ('classification=' + $noLeaseByPid[30976].classification)
    Confirm-That 'an expired lease also refuses the same identity' `
        ((Get-RecoveryLeaseVerdict -ProcId 30976 -StartTime '2026-09-03T12:20:31Z' `
            -ObservedAt '2099-01-02T00:00:00Z').Eligible -eq $false) `
        'expiry 2099-01-01 observed 2099-01-02'
    Confirm-That 'a lease naming another PID cannot authorize this identity' `
        ((Get-RecoveryLeaseVerdict -ProcId 999 -StartTime '2026-09-03T12:20:31Z' `
            -ObservedAt '2026-09-03T14:30:00Z').Eligible -eq $false) `
        'foreign lease refused'

    $Script:LeaseDir = $oldLeaseDir
    $env:SAISPIN_LEASE_DIR = $oldLeaseDir
    if (Test-Path -LiteralPath $leaseProbe) { Remove-Item -LiteralPath $leaseProbe -Recurse -Force -ErrorAction SilentlyContinue }

    # Non-ASCII names and paths must survive both pipes intact. On Windows
    # PowerShell 5.1 the default $OutputEncoding is ASCII, which turns every
    # such character into a question mark -- and the kill gate compares the
    # decision's image name against the live process, so a mangled name silently
    # blocks every action against that process forever.
    #
    # The probe strings are built from code points rather than written as
    # literals ON PURPOSE: this file has no BOM, and Windows PowerShell 5.1 reads
    # a BOM-less script as the ANSI codepage. A literal here would corrupt at
    # PARSE time on exactly the host the test exists to cover -- the check would
    # break, or worse, quietly compare mojibake to mojibake and pass. Escapes
    # make the source pure ASCII, so the value under test cannot be damaged by
    # how the file was saved. The two strings spell "piton.exe" and a path with
    # "Proekty/test.py" in Cyrillic.
    $cyrName = [regex]::Unescape('\u043F\u0438\u0442\u043E\u043D') + '.exe'
    $cyrPath = 'python C:\' + [regex]::Unescape('\u041F\u0440\u043E\u0435\u043A\u0442\u044B') +
        '\' + [regex]::Unescape('\u0442\u0435\u0441\u0442') + '.py'
    $unicode = @(
        [ordered]@{ pid = 424242; start_time = '2026-09-03T12:00:00Z'; name = $cyrName
            cpu_percent = 97.0; orphan = $true; observed_at = '2026-09-03T14:00:00Z'
            cmdline = $cyrPath; is_main_process = $false }
    )
    $round = Invoke-SaispinEngine -History @{} -Samples $unicode -ArmKill $false
    $intact = ($round.decisions[0].name -eq $cyrName -and
               $round.decisions[0].cmdline -eq $cyrPath)
    Confirm-That 'non-ASCII process names survive the engine round trip' `
        $intact $(if ($intact) { 'name and command line intact' } else { 'MANGLED by the pipe encoding' })

    # A rebuilt-after-corruption history must not be enough to kill.
    $Script:HistoryTrusted = $false
    try {
        $untrusted = Invoke-SaispinEngine -History $history -Samples $samples -ArmKill $true
        $untrustedKills = @($untrusted.decisions | Where-Object { $_.action -eq 'KILL' })
        Confirm-That 'an untrusted history downgrades every kill to an alert' `
            ($untrustedKills.Count -eq 0) ('KILL decisions=' + $untrustedKills.Count)
    } finally {
        $Script:HistoryTrusted = $true
    }
}

# ----------------------------------------------------------------- entry point

if ($SelfTest) {
    Invoke-SelfTest
    exit $(if ($script:selfTestFailures -eq 0) { 0 } else { 1 })
}

$normalizedOutput = & $PythonExe $EngineFile --normalize-settings $ConfigFile 2>&1
$settingsExit = $LASTEXITCODE
if ($settingsExit -eq 0) {
    try {
        $normalized = ($normalizedOutput | Out-String) | ConvertFrom-Json
        $Script:Settings = $normalized.settings
        if ($normalized.warning) {
            $Script:SettingsFallback = $true
            Write-SaispinLog -Level WARN -Text ('settings warning; safe defaults applied: ' + $normalized.warning)
        }
    } catch {
        $Script:SettingsFallback = $true
        Write-SaispinLog -Level WARN -Text ('settings response invalid; safe defaults applied: ' + $_.Exception.Message)
    }
} else {
    $Script:SettingsFallback = $true
    Write-SaispinLog -Level WARN -Text ('settings engine failed; safe defaults applied (exit ' + $settingsExit + ')')
}
$Script:SampleSeconds = [int]$Script:Settings.timing.sample_seconds
$Script:NotifyReminderSeconds = [int]$Script:Settings.notifications.reminder_minutes * 60
$Script:Allowlist = @($Script:Settings.allowlist)

# Dry-run is the default AND wins a contradiction: -DryRun -AutoKill terminates
# nothing. The one way to arm the watchdog is -AutoKill on its own.
$armKill = $AutoKill.IsPresent -and -not $DryRun.IsPresent

# Task Scheduler can fire a new instance while the previous one is still
# sampling. The mutex makes the second one a no-op instead of a second watcher
# racing the same state file.
$created = $false
$mutex = $null
try {
    $mutex = New-Object System.Threading.Mutex($true, $MutexName, [ref]$created)
} catch {
    # Cannot even create the mutex (access denied under a locked-down account):
    # treat it as held. A watcher that cannot prove it is alone does not run.
    Write-SaispinLog -Level WARN -Text ('mutex unavailable, not starting: ' + $_.Exception.Message)
    exit 0
}
if (-not $created) { exit 0 }

try {
    Invoke-Sweep -ArmKill ($armKill -and -not $TestSweep.IsPresent) -TestOnly $TestSweep.IsPresent
    exit $Script:SweepExitCode
} catch {
    Write-SaispinLog -Level ERROR -Text ('sweep failed: ' + $_.Exception.Message)
    exit 1
} finally {
    try { $mutex.ReleaseMutex() } catch { }
    try { $mutex.Dispose() } catch { }
}

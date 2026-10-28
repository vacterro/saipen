# saipen scheduled injector -- headless body of the 'saipen-inject' task.
# A background run never updates its development clone. It accepts only a
# clean worktree, snapshots one committed HEAD, rechecks source stability, and
# injects from that immutable snapshot. Refusals leave installed configs alone.

param([string]$CloneRoot = (Split-Path $PSScriptRoot -Parent))

$ErrorActionPreference = "Stop"
$logDir = Join-Path $env:LOCALAPPDATA "saipen"
try {
  [System.IO.Directory]::CreateDirectory($logDir) | Out-Null
} catch {
  Write-Host "FATAL: scheduler log directory unavailable: $($_.Exception.Message)"
  exit 1
}
$log = Join-Path $logDir "inject.log"
$runId = [System.Guid]::NewGuid().ToString("N")
$archive = Join-Path $logDir ("source-{0}.zip" -f $runId)
$snapshot = Join-Path $logDir ("source-{0}" -f $runId)
$raw = Join-Path $logDir ("inject-{0}.log" -f $runId)
$published = Join-Path $logDir "scheduled-source"
$previous = Join-Path $logDir "scheduled-source-previous"
$publishedChanged = $false
# T-1951: set once the pre-run binding snapshot exists. Declared here so every
# exit path -- including a refusal before the swap -- can leave without it.
$bindingManifest = $null

function Write-Log([string]$msg) {
  $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
  Add-Content -LiteralPath $log -Value $line -Encoding utf8
}

function Remove-RunFiles {
  $ok = $true
  foreach ($path in @($raw, $archive, $snapshot)) {
    if (Test-Path -LiteralPath $path) {
      try {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
      } catch {
        Write-Log "cleanup: failed $path -- $($_.Exception.Message)"
        $ok = $false
      }
    }
  }
  return $ok
}

function Get-PublishedState {
  # T-1951: what the published path ACTUALLY holds right now. The rollback
  # removes `published` before it knows whether `previous` exists, so a machine
  # that had not published before keeps NO generation at that path -- while the
  # PATH launcher and every installed hook `--saipen-root` still name it. Both
  # of those are deliberately stable paths, so the question a rollback changes
  # is never the spelling, only whether anything loadable is there.
  if (-not (Test-Path -LiteralPath $published)) { return "absent" }
  if (-not (Test-Path -LiteralPath (Join-Path $published "tools\saipen.py") -PathType Leaf)) {
    return "incomplete"
  }
  return "present"
}

function Get-BindingState {
  # "bound" means the path every launcher and hook config names resolves to a
  # generation. "dangling" means it does not, and a record that does not say so
  # is the tidy name the incident hid behind.
  if ((Get-PublishedState) -eq "present") { return "bound" }
  return "dangling"
}

function Restore-PublishedSource {
  $ok = $true
  try {
    if (Test-Path -LiteralPath $previous) {
      # There IS a known-good generation to go back to, so the rejected tree
      # must not stay where every launcher names it.
      if (Test-Path -LiteralPath $published) {
        Remove-Item -LiteralPath $published -Recurse -Force -ErrorAction Stop
      }
      Move-Item -LiteralPath $previous -Destination $published -ErrorAction Stop
    } elseif (Test-Path -LiteralPath $published) {
      # T-1951: NO previous generation exists (a machine's first publish, or a
      # failure before one was ever kept). Deleting `published` here leaves the
      # PATH launcher and every installed hook `--saipen-root` naming a path
      # with nothing in it, and a host whose hook cannot import answers
      # ENGINE_UNREACHABLE for every operator prompt -- total protocol loss,
      # measured live. A rejected-but-complete generation is strictly better
      # than none: it still loads, and it names its own drift (RUNTIME_DRIFT
      # with the exact recovery) instead of failing silently.
      Write-Log "rollback: no previous generation to restore -- retained the rejected tree; binding stays loadable but is NOT proven current"
    }
    $script:publishedChanged = $false
  } catch {
    Write-Log "rollback: failed published source -- $($_.Exception.Message)"
    $ok = $false
  }
  $state = Get-PublishedState
  $binding = Get-BindingState
  Write-Log ("rollback: published_state={0} binding={1}" -f $state, $binding)
  if (-not $ok) { return $false }
  # The run's own success condition: the path every consumer names resolves.
  # A rollback that could not put anything back is still a rollback; what it
  # must not do is report the same thing as one that did.
  return ($binding -eq "bound")
}

function Get-BindingFiles([string[]]$sourceRoots) {
  # T-1951: every file whose BYTES have to agree with the generation that ends
  # up at the published path. The hook configs are deliberately NOT here: they
  # name the stable published path, so a rollback does not change their
  # spelling, and rewriting a whole host config would clobber whatever a
  # concurrent session wrote into it during the run.
  #
  # The guard ARTIFACT is here, and that is the defect this closes: measured
  # live, the injector writes the new guard while the rollback reverts the tree
  # to the old engine, and the installed hook then answers
  # {"code":"ENGINE_UNREACHABLE","detail":"runtime import failed: ImportError"}
  # for every operator prompt -- the new guard imports modules the reverted
  # engine does not ship.
  #
  # Both generations' registries are read: a hook the NEW generation retires
  # still has live bytes from the OLD one, and a hook the new generation ADDS
  # did not exist before the run -- which is exactly what a restore has to
  # undo.
  $seen = @{}
  $files = New-Object System.Collections.Generic.List[object]
  foreach ($root in @($sourceRoots)) {
    $registryPath = Join-Path $root "extensions\adapters\registry.json"
    if (-not (Test-Path -LiteralPath $registryPath)) { continue }
    try {
      $registry = Get-Content -LiteralPath $registryPath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
      Write-Log ("bindings: registry unreadable at {0} -- {1}" -f $root, $_.Exception.Message)
      continue
    }
    foreach ($adapter in @($registry.adapters)) {
      $install = $adapter.install
      if ($null -eq $install) { continue }
      if (-not ($install.PSObject.Properties.Name -contains "hook")) { continue }
      $hookSurface = [string]$install.hook
      if ([string]::IsNullOrWhiteSpace($hookSurface)) { continue }
      $label = "hook:" + [string]$adapter.id
      if ($seen.ContainsKey($label)) { continue }
      $seen[$label] = $true
      # `~` here is the operator's own profile, the same expansion the
      # injector uses, never this script's cwd.
      $live = $hookSurface
      if ($live.StartsWith("~/") -or $live.StartsWith("~\")) { $live = $live.Substring(2) }
      elseif ($live.StartsWith("~")) { $live = $live.Substring(1) }
      $live = (Join-Path $env:USERPROFILE $live.Replace('/', '\'))
      $files.Add([pscustomobject]@{ live = $live; label = $label })
    }
  }
  # The PATH launchers run `<published>\tools\saipen.py`, so their bytes are
  # bound to the generation too. Both platform spellings, both declared dirs.
  foreach ($dir in @((Join-Path $env:USERPROFILE "bin"), (Join-Path $env:USERPROFILE ".local\bin"))) {
    foreach ($name in @("saipen.cmd", "saipen")) {
      $files.Add([pscustomobject]@{ live = (Join-Path $dir $name); label = ("launcher:" + $name) })
    }
  }
  return $files
}

function Backup-Bindings([string[]]$sourceRoots, [string]$backupRoot) {
  # Records BOTH states: the bytes to put back, and the fact that a file was
  # absent. A restore that cannot tell those apart turns "this machine never
  # had a Kiro hook" into "leave whatever is there now".
  $manifest = New-Object System.Collections.ArrayList
  foreach ($item in (Get-BindingFiles $sourceRoots)) {
    $entry = [ordered]@{ live = $item.live; label = $item.label; existed = $false; backup = $null }
    if (Test-Path -LiteralPath $item.live -PathType Leaf) {
      $safe = ($item.label -replace '[^A-Za-z0-9._-]', '_')
      # Two launcher directories can carry the same basename. Labels are
      # diagnostic, not unique identities; each entry needs its own backup.
      $target = Join-Path $backupRoot ("{0:D4}-{1}" -f $manifest.Count, $safe)
      try {
        [System.IO.Directory]::CreateDirectory($backupRoot) | Out-Null
        Copy-Item -LiteralPath $item.live -Destination $target -Force -ErrorAction Stop
        $entry.existed = $true
        $entry.backup = $target
      } catch {
        Write-Log ("bindings: cannot back up {0} -- {1}" -f $item.live, $_.Exception.Message)
        # An unreadable original is not an absent file. A partial manifest
        # could otherwise erase it on rollback, so refuse before publication.
        return $null
      }
    }
    [void]$manifest.Add($entry)
  }
  $path = Join-Path $backupRoot "bindings.json"
  try {
    [System.IO.Directory]::CreateDirectory($backupRoot) | Out-Null
    [System.IO.File]::WriteAllText($path, ($manifest | ConvertTo-Json -Depth 4),
      (New-Object System.Text.UTF8Encoding($false)))
  } catch {
    Write-Log ("bindings: manifest not written -- {0}" -f $_.Exception.Message)
    return $null
  }
  Write-Log ("bindings: snapshotted {0} surface(s) -- {1}" -f $manifest.Count, $path)
  return $path
}

function Restore-Bindings([string]$manifestPath) {
  # Put the pre-run bytes back, so the guard artifact and the launcher agree
  # with the generation the rollback left at the published path. Never raises:
  # a binding that cannot be restored is reported, and the caller's exit code
  # already says the run failed.
  if ([string]::IsNullOrWhiteSpace($manifestPath) -or
      -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    Write-Log "bindings: nothing to restore (no pre-run snapshot)"
    return $false
  }
  $restored = 0
  $failed = 0
  try {
    $entries = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
  } catch {
    Write-Log ("bindings: manifest unreadable -- {0}" -f $_.Exception.Message)
    return $false
  }
  foreach ($entry in @($entries)) {
    try {
      $live = [string]$entry.live
      if ([bool]$entry.existed) {
        $backup = [string]$entry.backup
        if (-not (Test-Path -LiteralPath $backup -PathType Leaf)) {
          throw "backup missing: $backup"
        }
        $parent = Split-Path -Parent $live
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
          [System.IO.Directory]::CreateDirectory($parent) | Out-Null
        }
        Copy-Item -LiteralPath $backup -Destination $live -Force -ErrorAction Stop
      } elseif (Test-Path -LiteralPath $live -PathType Leaf) {
        # It did not exist before this run, so the run's own write is what a
        # rollback must undo.
        Remove-Item -LiteralPath $live -Force -ErrorAction Stop
      }
      $restored++
    } catch {
      $failed++
      Write-Log ("bindings: cannot restore {0} -- {1}" -f [string]$entry.live, $_.Exception.Message)
    }
  }
  Write-Log ("bindings: restored={0} failed={1}" -f $restored, $failed)
  return ($failed -eq 0)
}

function Write-ConvergenceRecord([string]$head, [string]$publication, [string]$recordPath) {
  # T-1613: PUBLICATION and CONSUMER CONVERGENCE are two questions and this
  # record is where both answers live. Collapsing them into one boolean is
  # what produced the incident: a locked, non-blocking plugin directory made a
  # valid published generation look like a failed publication, and the rollback
  # that followed left consumer homes on the NEW generation while
  # scheduled-source went back to the old one -- generation skew under a
  # tidier name. Nothing here decides anything; it records what the two
  # components already decided, so no reader has to infer one from the other.
  $record = $null
  if (Test-Path -LiteralPath $recordPath) {
    try {
      $record = Get-Content -LiteralPath $recordPath -Raw -Encoding utf8 | ConvertFrom-Json
    } catch {
      $record = $null
    }
  }
  $consumers = @()
  $pending = @()
  $verdict = "CURRENT"
  if ($null -ne $record) {
    if ($record.PSObject.Properties.Name -contains "consumers") { $consumers = @($record.consumers) }
    if ($record.PSObject.Properties.Name -contains "pending") { $pending = @($record.pending) }
    if ($record.PSObject.Properties.Name -contains "convergence") { $verdict = [string]$record.convergence }
  }
  if ($pending.Count -gt 0 -and $verdict -eq "CURRENT") { $verdict = "DEGRADED" }
  $summary = [ordered]@{
    schema           = "SAIPEN_CONVERGENCE_1"
    generated_at     = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    published_head   = $head
    publication      = $publication
    convergence      = $verdict
    # T-1951: does the path every launcher and installed hook names resolve to
    # a generation? Separate from `publication`, which answers whether THIS run
    # published. A reader that collapses them reports a healthy machine while
    # every operator prompt fails to reach an engine.
    binding          = (Get-BindingState)
    consumers        = $consumers
    pending          = $pending
    pending_consumers = $pending
    requires_human   = $false
    retry            = "scheduled"
  }
  if ($summary.binding -ne "bound") {
    # Only a human can put a generation back once the path is empty, so this is
    # the one rollback shape that must ask instead of retrying forever.
    $summary.requires_human = $true
    $summary.retry = "human: reinstall the published source, then run 'saipen host repair'"
  }
  try {
    [System.IO.File]::WriteAllText($recordPath, ($summary | ConvertTo-Json -Depth 6), (New-Object System.Text.UTF8Encoding($false)))
  } catch {
    Write-Log "convergence: record not written -- $($_.Exception.Message)"
  }
  $shortHead = if ($head.Length -ge 8) { $head.Substring(0, 8) } else { $head }
  Write-Log ("convergence: head={0} publication={1} convergence={2} pending={3} requires_human=false" -f `
    $shortHead, $publication, $verdict, $pending.Count)
}

function Stop-Run([string]$message, [int]$code) {
  Write-Log $message
  $cleanupOk = Remove-RunFiles
  # T-1951: a refusal here never swapped the published source, so the binding
  # snapshot describes a machine nothing was written against yet. The rollback
  # path exits without calling Stop-Run precisely so it keeps its snapshot.
  if ($script:bindingManifest) {
    $dir = Split-Path -Parent $script:bindingManifest
    if (Test-Path -LiteralPath $dir) {
      try { Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction Stop }
      catch { Write-Log ("bindings: snapshot not cleaned -- {0}" -f $_.Exception.Message) }
    }
  }
  if (-not $cleanupOk -and $code -eq 0) { $code = 1 }
  Write-Log "=== end rc=$code ==="
  exit $code
}

function Invoke-Git([string[]]$Arguments) {
  $output = @(& $script:GitPath @Arguments 2>&1)
  $rc = $LASTEXITCODE
  return [pscustomobject]@{ Rc = $rc; Output = @($output | ForEach-Object { "$_" }) }
}

function Get-InjectedSurface([string]$sourceRoot) {
  # The paths the injector actually copies, read from the ONE owner of that
  # list: saipen/MANIFEST.json. Duplicating it here would drift, and a drifted
  # copy would either block on something harmless or -- far worse -- publish an
  # edited protocol file this check no longer watches.
  $manifestPath = Join-Path $sourceRoot "saipen/MANIFEST.json"
  if (-not (Test-Path -LiteralPath $manifestPath)) {
    Stop-Run "REFUSE: MANIFEST_MISSING $manifestPath" 1
  }
  try {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
  } catch {
    Stop-Run "REFUSE: MANIFEST_UNREADABLE $($_.Exception.Message)" 1
  }
  $surface = New-Object System.Collections.Generic.List[string]
  foreach ($tree in @($manifest.copy_trees)) { if ($tree.src) { $surface.Add([string]$tree.src) } }
  foreach ($file in @($manifest.files)) { if ($file.src) { $surface.Add([string]$file.src) } }
  # The manifest decides what ships, so an edit to it is an edit to the surface.
  $surface.Add("saipen/MANIFEST.json")
  if ($surface.Count -eq 0) {
    Stop-Run "REFUSE: MANIFEST_EMPTY_SURFACE" 1
  }
  return ($surface | Sort-Object -Unique)
}

function Read-CleanStatus([string]$sourceRoot) {
  # T-1251: the guard exists so an EDITED PROTOCOL is never published to the
  # consumer homes. It used to reject any line of `git status -uall`, which on
  # a live project means the translation cache, the subSaipen kitchens, the
  # improve cycles and the user's own notes -- thousands of untracked files
  # that change nothing about what gets copied. The task was healthy, fired
  # every 15 minutes, and skipped every single time: a feature shipped inert.
  # Scoping the question to the injected surface keeps the property that
  # matters (an unstaged saipen/CORE.md still blocks) and drops the one that
  # made it useless.
  $surface = Get-InjectedSurface $sourceRoot
  $result = Invoke-Git (@("-C", $sourceRoot, "status", "--porcelain=v1",
                          "--untracked-files=all", "--") + $surface)
  if ($result.Rc -ne 0) {
    foreach ($line in $result.Output) { Write-Log ("status: " + $line) }
    Stop-Run "REFUSE: SOURCE_STATUS_FAILED rc=$($result.Rc)" 1
  }
  if (($result.Output -join "").Length -gt 0) {
    Write-Log ("surface: " + ($surface -join " "))
    foreach ($line in $result.Output) { Write-Log ("dirty: " + $line) }
    Stop-Run "SKIP: DIRTY_SOURCE" 2
  }
  Write-Log ("clean: injected surface matches HEAD (" + $surface.Count + " path(s))")
}

Write-Log "=== saipen scheduled inject run=$runId ==="
$env:GIT_OPTIONAL_LOCKS = "0"
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
  Stop-Run "REFUSE: GIT_UNAVAILABLE" 1
}
$GitPath = $git.Source

$rootResult = Invoke-Git @("-C", $CloneRoot, "rev-parse", "--show-toplevel")
if ($rootResult.Rc -ne 0 -or $rootResult.Output.Count -ne 1) {
  foreach ($line in $rootResult.Output) { Write-Log ("root: " + $line) }
  Stop-Run "REFUSE: SOURCE_ROOT_UNAVAILABLE rc=$($rootResult.Rc)" 1
}
$sourceRoot = $rootResult.Output[0].Trim()
try {
  $requestedRoot = [System.IO.Path]::GetFullPath(
    (Resolve-Path -LiteralPath $CloneRoot).Path).TrimEnd('\', '/')
  $resolvedRoot = [System.IO.Path]::GetFullPath($sourceRoot).TrimEnd('\', '/')
} catch {
  Stop-Run "REFUSE: SOURCE_ROOT_INVALID $($_.Exception.Message)" 1
}
if (-not $requestedRoot.Equals(
    $resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  Stop-Run "REFUSE: SOURCE_ROOT_MISMATCH requested=$requestedRoot git=$resolvedRoot" 1
}

Read-CleanStatus $sourceRoot
$headResult = Invoke-Git @("-C", $sourceRoot, "rev-parse", "--verify", "HEAD")
if ($headResult.Rc -ne 0 -or $headResult.Output.Count -ne 1) {
  Stop-Run "REFUSE: SOURCE_HEAD_UNAVAILABLE rc=$($headResult.Rc)" 1
}
$head = $headResult.Output[0].Trim()
Write-Log "source: HEAD $head"

try {
  $archiveResult = Invoke-Git @("-C", $sourceRoot, "archive", "--format=zip",
                                "--output=$archive", $head)
  if ($archiveResult.Rc -ne 0) {
    foreach ($line in $archiveResult.Output) { Write-Log ("archive: " + $line) }
    Stop-Run "REFUSE: SOURCE_SNAPSHOT_FAILED rc=$($archiveResult.Rc)" 1
  }
  Expand-Archive -LiteralPath $archive -DestinationPath $snapshot -Force

  # Catch edits or branch movement during preflight. Injection below reads only
  # the archive, so even a later edit can never produce a mixed-source install.
  Read-CleanStatus $sourceRoot
  $headAfter = Invoke-Git @("-C", $sourceRoot, "rev-parse", "--verify", "HEAD")
  if ($headAfter.Rc -ne 0 -or $headAfter.Output.Count -ne 1 -or
      $headAfter.Output[0].Trim() -ne $head) {
    Stop-Run "SKIP: SOURCE_CHANGED" 2
  }

  $injector = Join-Path $snapshot "bootstrap\inject.ps1"
  if (-not (Test-Path -LiteralPath $injector)) {
    Stop-Run "REFUSE: SNAPSHOT_INJECTOR_MISSING head=$head" 1
  }

  # Config blocks written by inject.ps1 name its SkillHome. Publish the exact
  # archived tree at one persistent path before invoking it; a temporary source
  # path would become dangling as soon as this run cleaned up.
  if (Test-Path -LiteralPath $previous) {
    Stop-Run "REFUSE: PUBLISHED_SOURCE_BACKUP_EXISTS path=$previous" 1
  }
  # T-1951: snapshot the binding surfaces BEFORE anything is swapped. The
  # injector rewrites the guard artifact and the PATH launchers during the run;
  # if this run then rolls back, those bytes name a generation the published
  # path no longer carries and the installed hook stops importing. The snapshot
  # must therefore be the PRE-RUN bytes, read while `published` still holds the
  # generation the live hooks were written against -- taking it after the swap
  # would capture exactly what the rollback has to undo. Both generations'
  # registries are read so a hook the new generation ADDS is also undone.
  $bindingRoots = @()
  if (Test-Path -LiteralPath $published) { $bindingRoots += $published }
  $bindingRoots += $snapshot
  $bindingManifest = Backup-Bindings $bindingRoots (Join-Path $logDir ("bindings-{0}" -f $runId))
  if (-not $bindingManifest) {
    throw "Binding snapshot failed; publication not started"
  }

  if (Test-Path -LiteralPath $published) {
    Move-Item -LiteralPath $published -Destination $previous -ErrorAction Stop
  }
  Move-Item -LiteralPath $snapshot -Destination $published -ErrorAction Stop
  $publishedChanged = $true

  $injector = Join-Path $published "bootstrap\inject.ps1"
  & powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass `
    -File $injector *> $raw
  $rc = $LASTEXITCODE
  if (Test-Path -LiteralPath $raw) {
    Get-Content -LiteralPath $raw | ForEach-Object { Write-Log ("inject: " + $_) }
  }
  if ($null -eq $rc) { $rc = 0 }
  Write-Log "inject: head=$head exit=$rc"
  # T-1613: the injector's exit code now answers ONE question -- did a
  # consumer the adapter registry declares BLOCKING fail to converge? A
  # non-blocking consumer that is locked, busy or absent no longer rolls a
  # valid publication back; it is recorded as pending and the next scheduled
  # run converges it. Rollback stays for failures that invalidate the
  # PUBLICATION itself, which are refused before this point or reported here
  # as a blocking failure.
  if ($rc -ne 0) {
    # T-1951: the rollback answers "is there still a generation at the path
    # every launcher and hook config names?". The exit code answers "did this
    # run publish?". They are separate facts, so the record reports both
    # instead of letting one stand in for the other.
    $restored = Restore-PublishedSource
    if (-not $restored) { $rc = 1 }
    # The source went back, so the bytes that were written against the NEW
    # generation have to go back with it -- otherwise the guard and launcher
    # disagree with the engine they delegate to and every operator prompt
    # fails to reach one.
    if (-not (Restore-Bindings $bindingManifest)) { $rc = 1 }
    Write-ConvergenceRecord $head "ROLLED_BACK" (Join-Path $logDir "convergence.json")
    Write-Log ("rollback: binding={0} launchers_and_hooks_named={1}" -f `
      (Get-BindingState), $published)
  } else {
    Write-ConvergenceRecord $head "CURRENT" (Join-Path $logDir "convergence.json")
    # T-1252: inject.ps1 copies the protocol but writes no freshness stamp, so
    # every refreshed home read as "installed unstamped" forever and a drifted
    # copy was indistinguishable from a current one. The digest has exactly one
    # owner, tools/autoinject.py, so the stamp is written by calling it rather
    # than by a second implementation here that would drift from it. A missing
    # interpreter is logged and left visible: the COPY is good, only its
    # witness is absent, and `autoinject.py --check` says so out loud instead
    # of this run pretending it stamped something.
    $stamper = Join-Path $published "tools\autoinject.py"
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $python) {
      Write-Log "stamp: SKIPPED no python on PATH -- copies are current but unstamped"
    } elseif (-not (Test-Path -LiteralPath $stamper)) {
      Write-Log "stamp: SKIPPED tools/autoinject.py absent from the published source"
    } else {
      $stampOutput = @(& $python.Source $stamper "--stamp-only" "--source-head" $head 2>&1)
      $stampRc = $LASTEXITCODE
      foreach ($line in $stampOutput) { Write-Log ("stamp: " + $line) }
      if ($stampRc -ne 0) { Write-Log "stamp: FAILED rc=$stampRc" }
    }
    try {
      if (Test-Path -LiteralPath $previous) {
        Remove-Item -LiteralPath $previous -Recurse -Force -ErrorAction Stop
      }
      $publishedChanged = $false
    } catch {
      Write-Log "cleanup: failed previous published source -- $($_.Exception.Message)"
      $rc = 1
    }
    # T-1951: this run published, so the bytes the injector wrote are the bytes
    # that belong beside it. The pre-run snapshot is kept only on the rollback
    # path, where it is the thing a rollback restores.
    if ($bindingManifest) {
      $bindingDir = Split-Path -Parent $bindingManifest
      if (Test-Path -LiteralPath $bindingDir) {
        try { Remove-Item -LiteralPath $bindingDir -Recurse -Force -ErrorAction Stop }
        catch { Write-Log ("bindings: snapshot not cleaned -- {0}" -f $_.Exception.Message) }
      }
    }
  }
  $cleanupOk = Remove-RunFiles
  if (-not $cleanupOk -and $rc -eq 0) { $rc = 1 }
  Write-Log "=== end rc=$rc ==="
  exit $rc
} catch {
  if ($publishedChanged -or (Test-Path -LiteralPath $previous)) {
    [void](Restore-PublishedSource)
    if ($bindingManifest) { [void](Restore-Bindings $bindingManifest) }
  }
  Stop-Run "REFUSE: PREFLIGHT_FAILED $($_.Exception.Message)" 1
}

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
# Raw .NET File APIs take the path as a plain string, and on Unix a
# backslash is a legal filename character, not a directory separator --
# PowerShell cmdlets normalize the Windows-style paths below, but
# [System.IO.File] does not, so every raw .NET call gets the
# platform-native spelling.
function Get-NativePath([string]$path) {
  return $path.Replace('\', [System.IO.Path]::DirectorySeparatorChar)
}

function Resolve-HostSurface([string]$path) {
  if ($env:CLAUDE_CONFIG_DIR -and ($path -eq '~/.claude' -or $path.StartsWith('~/.claude/'))) {
    return Get-NativePath (Join-Path $env:CLAUDE_CONFIG_DIR $path.Substring(9).TrimStart('/'))
  }
  return Get-NativePath ($path.Replace('~', $h))
}

function Remove-Block([string]$file) {
  if (Test-Path $file) {
    if (-not (Test-Path $file -PathType Leaf)) { throw "config path is not a file: $file" }
    $bytes = [System.IO.File]::ReadAllBytes((Get-NativePath $file))
    $text = [System.Text.Encoding]::GetEncoding(28591).GetString($bytes)
    $match = [regex]::Match($text, '(?s)(?:\r\n|\n)?<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->(?:\r\n|\n)?')
    if ($match.Success) {
      $clean = $text.Substring(0, $match.Index) + $text.Substring($match.Index + $match.Length)
      # Backup the file before uninstalling just in case
      Copy-Item $file "$file.uninstalled.bak" -Force -ErrorAction Stop
      [System.IO.File]::WriteAllBytes((Get-NativePath $file), [System.Text.Encoding]::GetEncoding(28591).GetBytes($clean))
      return "block removed"
    }
  }
  return "clean"
}

function Resolve-Python {
  # The interpreter that exact, ownership-checked removal is delegated to, or
  # $null. A machine without a working one is exactly the machine on which an
  # installed hook cannot start either, so it must still be able to take
  # SAIPEN's hooks out. This used to be `Get-Command python -ErrorAction Stop`:
  # with no interpreter the uninstaller ended on that line and removed nothing,
  # not even the instruction blocks that never needed one.
  $candidate = $null
  if ($env:SAIPEN_PYTHON) {
    $candidate = $env:SAIPEN_PYTHON
  } else {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { $candidate = $command.Source }
  }
  if (-not $candidate) { return $null }
  try {
    # A name that resolves is not an interpreter that runs: the Windows Store
    # alias resolves and starts nothing.
    & $candidate -B -c "import hashlib, json" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return $candidate }
  } catch { }
  return $null
}

function Test-Link([string]$path) {
  $item = Get-Item -LiteralPath $path -Force
  return [bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

function Get-Sha256([byte[]]$bytes) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  try {
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
  } finally { $sha.Dispose() }
}

function Get-FileSha256([string]$path) {
  return Get-Sha256 ([System.IO.File]::ReadAllBytes((Get-NativePath $path)))
}

function Get-ContentSha256([string]$path) {
  # The shipped CONTENT of a text artifact: LF line endings, the one
  # normalisation the installer compares by (a clone holds LF, a checkout made
  # by git on Windows holds CRLF). Binary content stays byte-exact.
  $bytes = [System.IO.File]::ReadAllBytes((Get-NativePath $path))
  if ([System.Array]::IndexOf($bytes, [byte]0) -ge 0) { return Get-Sha256 $bytes }
  $latin = [System.Text.Encoding]::GetEncoding(28591)
  return Get-Sha256 ($latin.GetBytes($latin.GetString($bytes).Replace("`r`n", "`n")))
}

function Remove-EmptyDirectories([string]$root) {
  # Never through a link: a junction inside the skill home names a directory
  # that is not this installation's to prune.
  foreach ($child in @(Get-ChildItem -LiteralPath $root -Directory -Force)) {
    if ($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { continue }
    Remove-EmptyDirectories $child.FullName
    if (@(Get-ChildItem -LiteralPath $child.FullName -Force).Count -eq 0) {
      Remove-Item -LiteralPath $child.FullName -Force
    }
  }
}

function Remove-SkillNative([string]$path) {
  # `install_ownership.py remove` without an interpreter, by the same rule: a
  # file goes only while its bytes still equal the digest the installer
  # recorded. Unknown and edited files survive, and a home with no ledger is a
  # legacy install that is preserved whole.
  if (Test-Link $path) { throw "installation root is a link: $path" }
  $ledgerPath = Join-Path $path ".saipen_install.json"
  if (-not (Test-Path -LiteralPath $ledgerPath -PathType Leaf)) {
    return "legacy skill preserved whole (no ownership ledger)"
  }
  $ledger = [System.IO.File]::ReadAllText((Get-NativePath $ledgerPath)) | ConvertFrom-Json
  if ($ledger.schema_version -ne 1 -or $ledger.files -isnot [System.Management.Automation.PSCustomObject]) {
    throw "invalid installation ownership ledger"
  }
  $root = (Resolve-Path -LiteralPath $path).ProviderPath
  # Every path is checked before the first destructive operation.
  $doomed = @()
  foreach ($entry in $ledger.files.PSObject.Properties) {
    $relative = [string]$entry.Name
    $parts = $relative.Split('/')
    if (-not $relative -or $relative.Contains('\') -or $relative.Contains(':') -or
        @($parts | Where-Object { $_ -in @('', '.', '..') }).Count -gt 0 -or
        [string]$entry.Value -notmatch '^[0-9a-f]{64}$') {
      throw "unsafe installation ownership entry"
    }
    $file = Join-Path $root ($parts -join [System.IO.Path]::DirectorySeparatorChar)
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
    if (Test-Link $file) { throw "installation ownership path is a link: $relative" }
    if ((Get-FileSha256 $file) -eq [string]$entry.Value) { $doomed += $file }
  }
  foreach ($file in $doomed) { Remove-Item -LiteralPath $file -Force }
  Remove-Item -LiteralPath $ledgerPath -Force
  Remove-EmptyDirectories $root
  if (@(Get-ChildItem -LiteralPath $root -Force).Count -eq 0) {
    Remove-Item -LiteralPath $root -Force
    return "skill removed natively (removed=$($doomed.Count), nothing preserved)"
  }
  return "skill removed natively; unowned/edited files preserved (removed=$($doomed.Count))"
}

function Remove-Skill([string]$path) {
  if (Test-Path $path) {
    try {
      if (-not $script:Python) { return (Remove-SkillNative $path) }
      $result = & $script:Python -B (Join-Path $PSScriptRoot "install_ownership.py") remove (Get-NativePath $path) 2>&1
      if ($LASTEXITCODE -ne 0) { throw "ownership cleanup: $result" }
      return "skill removed; unowned/edited files preserved ($result)"
    } catch {
      return "remove FAILED ($path): $($_.Exception.Message)"
    }
  }
  return "clean"
}

function Remove-PathLauncherNative([string]$homeDir) {
  # `install_ownership.py remove-launcher` without an interpreter: a launcher
  # goes only while its bytes equal the digest the engine recorded, and only
  # from a declared per-user directory under this home (T-1678).
  $record = Join-Path $homeDir ".saipen\path-launcher.json"
  $doc = [System.IO.File]::ReadAllText((Get-NativePath $record)) | ConvertFrom-Json
  if ($doc.files -isnot [System.Management.Automation.PSCustomObject]) {
    throw "invalid PATH launcher record"
  }
  $allowed = @(
    [System.IO.Path]::GetFullPath((Join-Path $homeDir "bin")),
    [System.IO.Path]::GetFullPath((Join-Path $homeDir ".local\bin"))
  )
  $removed = 0
  foreach ($entry in $doc.files.PSObject.Properties) {
    $file = [string]$entry.Name
    if (-not [System.IO.Path]::IsPathRooted($file)) { continue }
    $parent = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($file))
    $name = [System.IO.Path]::GetFileName($file).ToLowerInvariant()
    if (($allowed -notcontains $parent) -or ($name -notin @("saipen", "saipen.cmd"))) { continue }
    if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Test-Link $file)) { continue }
    if ((Get-FileSha256 $file) -eq [string]$entry.Value) {
      Remove-Item -LiteralPath $file -Force
      $removed += 1
    }
  }
  Remove-Item -LiteralPath $record -Force
  return "PATH launcher removed natively (removed=$removed)"
}

function Remove-PathLauncher([string]$homeDir) {
  if (-not (Test-Path -LiteralPath (Join-Path $homeDir ".saipen\path-launcher.json") -PathType Leaf)) {
    return "clean"
  }
  try {
    if (-not $script:Python) { return (Remove-PathLauncherNative $homeDir) }
    $result = & $script:Python -B (Join-Path $PSScriptRoot "install_ownership.py") remove-launcher (Get-NativePath $homeDir) 2>&1
    if ($LASTEXITCODE -ne 0) { throw "ownership cleanup: $result" }
    return "PATH launcher removed; edited files preserved ($result)"
  } catch {
    return "remove FAILED (PATH launcher): $($_.Exception.Message)"
  }
}

function Get-SchedulerTask([string]$Name) {
  $queryErrors = @()
  $task = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue `
    -ErrorVariable +queryErrors
  $unexpected = @($queryErrors | Where-Object {
    $_.CategoryInfo.Category -ne [System.Management.Automation.ErrorCategory]::ObjectNotFound
  })
  if ($unexpected.Count -gt 0) {
    throw "could not query $Name`: $($unexpected[0].Exception.Message)"
  }
  return $task
}

function Test-SchedulerTaskWithSchtasks([string]$Name) {
  schtasks /Query /TN $Name 2>&1 | Out-Null
  $specificRc = $LASTEXITCODE
  if ($specificRc -eq 0) { return $true }
  # A successful all-task query proves Task Scheduler is reachable, so only
  # this name is absent. Two failed queries mean unknown service/access state.
  schtasks /Query /FO CSV /NH 2>&1 | Out-Null
  $allRc = $LASTEXITCODE
  if ($allRc -eq 0) { return $false }
  throw "could not query $Name (schtasks rc $specificRc; all-task query rc $allRc)"
}

function Remove-Task() {
  # Remove the auto-scheduled inject task (T-531) when uninstalling, so a
  # de-advertised protocol does not keep pulling + injecting every 15 minutes.
  # Windows-only: Get-ScheduledTask does not exist on pwsh/Linux, and a host
  # that never ran the scheduler has nothing to remove -- both are clean. The
  # sandboxed injector probe sets SAIPEN_UNINSTALL_SKIP_TASK because the task
  # is machine-global and a test run must not delete real machine state.
  if ($env:SAIPEN_UNINSTALL_SKIP_TASK) { return "clean" }
  $hasScheduledTaskCmdlet = [bool](Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue)
  if (-not $hasScheduledTaskCmdlet -and
      -not (Get-Command schtasks -ErrorAction SilentlyContinue)) {
    return "clean"
  }
  $removed = @()
  $failures = @()
  foreach ($taskName in @("saipen-inject", "saipen-autoinject")) {
    try {
      if ($hasScheduledTaskCmdlet) {
        $present = [bool](Get-SchedulerTask $taskName)
      } else {
        $present = Test-SchedulerTaskWithSchtasks $taskName
      }
    } catch {
      $failures += $_.Exception.Message
      continue
    }
    if (-not $present) { continue }
    schtasks /Delete /TN $taskName /F 2>&1 | Out-Null
    $deleteRc = $LASTEXITCODE
    if ($deleteRc -eq 0) {
      $removed += $taskName
    } else {
      $failures += "$taskName rc $deleteRc"
    }
  }
  if ($failures.Count -gt 0) {
    return "task remove FAILED ($($failures -join ', ')); wrapper preserved"
  }
  $runtimeDir = Join-Path $env:LOCALAPPDATA "saipen"
  $runtimeWrapper = Join-Path $runtimeDir "schedule-run-hidden.vbs"
  $runtimeSource = Join-Path $runtimeDir "scheduled-source"
  try {
    if (Test-Path -LiteralPath $runtimeWrapper) {
      Remove-Item -LiteralPath $runtimeWrapper -Force -ErrorAction Stop
      $removed += "runtime wrapper"
    }
    if (Test-Path -LiteralPath $runtimeSource) {
      Remove-Item -LiteralPath $runtimeSource -Recurse -Force -ErrorAction Stop
      $removed += "runtime source"
    }
    if (Test-Path -LiteralPath $runtimeDir) {
      Get-ChildItem -LiteralPath $runtimeDir -Force -ErrorAction Stop |
        Where-Object {
          $_.Name -like "scheduled-source-previous*" -or
          $_.Name -like "source-*" -or
          $_.Name -like "inject-*.log"
        } |
        ForEach-Object {
          Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction Stop
          $removed += "runtime source backup"
        }
    }
  } catch {
    return "scheduler runtime remove FAILED ($runtimeDir): $($_.Exception.Message)"
  }
  if ($removed.Count -gt 0) { return "removed: $($removed -join ', ')" }
  return "clean"
}

function Remove-Aider([string]$file) {
  # Remove exactly the block the injector wrote (comment + read: key +
  # consecutive saipen BOOT/STYLE items), CRLF-tolerant -- never any other
  # read: line the user owns.
  if (Test-Path $file) {
    if (-not (Test-Path $file -PathType Leaf)) { throw "config path is not a file: $file" }
    $bytes = [System.IO.File]::ReadAllBytes((Get-NativePath $file))
    # Latin-1 maps one byte to one character, so regex indices are byte offsets.
    # Managed lines are ASCII; untouched BOM/non-UTF8/user bytes stay untouched.
    $byteText = [System.Text.Encoding]::GetEncoding(28591).GetString($bytes)
    $blockRe = '(?m)(?:^|\r?\n)# saipen protocol auto-loaded\r?\nread:\r?\n[ \t]*-[ \t][^\r\n]*saipen[\\/]BOOT\.md\r?\n[ \t]*-[ \t][^\r\n]*saipen[\\/]STYLE\.md(?:\r?\n)?'
    $match = [regex]::Match($byteText, $blockRe)
    if ($match.Success) {
      $clean = New-Object byte[] ($bytes.Length - $match.Length)
      [System.Buffer]::BlockCopy($bytes, 0, $clean, 0, $match.Index)
      $suffixLength = $bytes.Length - $match.Index - $match.Length
      if ($suffixLength -gt 0) {
        [System.Buffer]::BlockCopy($bytes, $match.Index + $match.Length,
          $clean, $match.Index, $suffixLength)
      }
      Copy-Item $file "$file.uninstalled.bak" -Force -ErrorAction Stop
      [System.IO.File]::WriteAllBytes((Get-NativePath $file), $clean)
      return "aider conf cleaned"
    } elseif ($byteText -match 'saipen[\\/]BOOT\.md') {
      return "manual aider conf (please remove manually)"
    }
  }
  return "clean"
}

$h = $env:USERPROFILE
$script:BootstrapFailed = $false
$script:Python = Resolve-Python

function Test-OwnedHookCommand($command, [string]$hostId, [string]$artifact) {
  # `install_host_guard._uninstall_entry_is_ours`, natively: an invocation of
  # THIS guard artifact for THIS host with a SAIPEN root -- never a mention of
  # the name inside a hook the operator wrote.
  if (-not ($command -is [string]) -or -not $command) { return $false }
  $flat = $command.Replace('\', '/').ToLowerInvariant()
  $want = $artifact.Replace('\', '/').ToLowerInvariant()
  if (-not $flat.Contains($want) -or -not $flat.Contains('--saipen-root')) { return $false }
  $named = '--host[ =]+["'']?' + [regex]::Escape($hostId.ToLowerInvariant()) + '(["''\s]|$)'
  return [regex]::IsMatch($flat, $named)
}

function Test-OwnedHookEntry($entry, [string]$hostId, [string]$artifact) {
  if ($entry -isnot [System.Management.Automation.PSCustomObject]) { return $false }
  $commands = @($entry.command, $entry.commandWindows)
  if ($entry.action -is [System.Management.Automation.PSCustomObject]) { $commands += $entry.action.command }
  foreach ($command in $commands) {
    if (Test-OwnedHookCommand $command $hostId $artifact) { return $true }
  }
  return $false
}

function Test-HostAlive {
  # `install_host_guard.host_alive`, natively. Unknown is yes: an inert file
  # left behind is free, a deleted script behind a loaded command is a lockout.
  if ($env:SAIPEN_UNINSTALL_HOST_ALIVE -eq "0") { return $false }
  if ($env:SAIPEN_UNINSTALL_HOST_ALIVE -eq "1") { return $true }
  try {
    # Which processes are alive is machine-global: only the profile the
    # operating system records is probed, never one an environment points at.
    $machineProfile = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
    if (-not $machineProfile -or
        [System.IO.Path]::GetFullPath($machineProfile).TrimEnd('\', '/') -ne
        [System.IO.Path]::GetFullPath($h).TrimEnd('\', '/')) {
      return $false
    }
    $registryPath = Join-Path (Split-Path $PSScriptRoot) "saipen\REGISTRY.json"
    $facts = [System.IO.File]::ReadAllText((Get-NativePath $registryPath)) | ConvertFrom-Json
    $images = @($facts.protocol_admission.host_authority.host_images)
    if ($images.Count -eq 0) { return $true }
    foreach ($image in $images) {
      $name = [System.IO.Path]::GetFileNameWithoutExtension([string]$image)
      if ($name -and (Get-Process -Name $name -ErrorAction SilentlyContinue)) { return $true }
    }
    return $false
  } catch {
    return $true
  }
}

function Remove-HookNative($adapter) {
  # `install_host_guard.py <host> --uninstall` without an interpreter. The hook
  # config is the operator's SHARED file: every entry that is not this guard's
  # stays, the bytes that were there are kept as `<config>.uninstalled.bak`,
  # and where the file returns to what the installer first found, those
  # original bytes are restored exactly. Returns the number of entries removed.
  $hostId = [string]$adapter.id
  $artifact = Resolve-HostSurface ([string]$adapter.hook_install_surface)
  $config = Resolve-HostSurface ([string]$adapter.hook_config_surface)
  foreach ($path in @($artifact, $config)) {
    if ((Test-Path -LiteralPath $path) -and (Test-Link $path)) {
      throw "hook uninstall path is a link: $path"
    }
  }
  $removed = 0
  if (Test-Path -LiteralPath $config -PathType Leaf) {
    $original = [System.IO.File]::ReadAllBytes($config)
    $data = [System.IO.File]::ReadAllText($config) | ConvertFrom-Json
    if ($data -isnot [System.Management.Automation.PSCustomObject]) { throw "hook config must be a JSON object: $config" }
    $hooks = $data.hooks
    if ($hooks -is [System.Array]) {
      # Kiro: one flat list of hook entries.
      $kept = @($hooks | Where-Object { -not (Test-OwnedHookEntry $_ $hostId $artifact) })
      $removed = $hooks.Count - $kept.Count
      $data.hooks = $kept
      $others = @($data.PSObject.Properties.Name | Where-Object { $_ -notin @("version", "hooks") })
      if ($removed -gt 0 -and $kept.Count -eq 0 -and $others.Count -eq 0) { $data = $null }
    } elseif ($hooks -is [System.Management.Automation.PSCustomObject]) {
      foreach ($eventName in @($hooks.PSObject.Properties.Name)) {
        $groups = $hooks.$eventName
        if ($groups -isnot [System.Array]) { throw "hook event must be an array: $eventName" }
        $keptGroups = @()
        foreach ($group in $groups) {
          if ($group -isnot [System.Management.Automation.PSCustomObject] -or $group.hooks -isnot [System.Array]) {
            throw "malformed hook group: $eventName"
          }
          $kept = @($group.hooks | Where-Object { -not (Test-OwnedHookEntry $_ $hostId $artifact) })
          $own = $group.hooks.Count - $kept.Count
          $removed += $own
          $extra = @($group.PSObject.Properties.Name | Where-Object { $_ -notin @("matcher", "hooks") })
          if ($kept.Count -gt 0 -or $own -eq 0 -or $extra.Count -gt 0) {
            $group.hooks = $kept
            $keptGroups += $group
          }
        }
        if ($keptGroups.Count -gt 0) {
          $hooks.$eventName = $keptGroups
        } elseif ($groups.Count -gt 0) {
          $hooks.PSObject.Properties.Remove($eventName)
        }
      }
      if ($removed -gt 0 -and @($hooks.PSObject.Properties).Count -eq 0) {
        $data.PSObject.Properties.Remove("hooks")
      }
    } elseif ($null -ne $hooks) {
      throw "hooks must be an object or an array: $config"
    }
    if ($removed -gt 0) {
      [System.IO.File]::WriteAllBytes("$config.uninstalled.bak", $original)
      $empty = ($null -eq $data) -or (@($data.PSObject.Properties).Count -eq 0)
      $wanted = if ($empty) { "{}" } else { ConvertTo-Json $data -Depth 100 -Compress }
      $restored = $false
      $pattern = '^' + [regex]::Escape((Split-Path $config -Leaf)) + '\.[0-9a-f]{16}\.bak$'
      $backups = @(Get-ChildItem -LiteralPath (Split-Path $config) -File -Force |
        Where-Object { $_.Name -match $pattern } | Sort-Object Name)
      foreach ($backup in $backups) {
        if ($backup.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { continue }
        try {
          $content = [System.IO.File]::ReadAllBytes($backup.FullName)
          $previous = [System.IO.File]::ReadAllText($backup.FullName) | ConvertFrom-Json
          if ((ConvertTo-Json $previous -Depth 100 -Compress) -eq $wanted) {
            [System.IO.File]::WriteAllBytes($config, $content)
            $restored = $true
            break
          }
        } catch { continue }
      }
      if (-not $restored) {
        if ($empty) {
          Remove-Item -LiteralPath $config -Force
        } else {
          [System.IO.File]::WriteAllText($config, (ConvertTo-Json $data -Depth 100) + "`n", $Utf8NoBom)
        }
      }
    }
  }
  if (Test-Path -LiteralPath $artifact -PathType Leaf) {
    $shipped = Get-NativePath (Join-Path (Split-Path $PSScriptRoot) ([string]$adapter.hook_artifact))
    $retired = Get-NativePath (Join-Path (Split-Path $PSScriptRoot) "tools\retired_host_hook.py")
    $installed = Get-ContentSha256 $artifact
    if ($installed -eq (Get-ContentSha256 $shipped) -or $installed -eq (Get-ContentSha256 $retired)) {
      if (Test-HostAlive) {
        # A running host keeps the hook command it loaded at start, and a
        # command whose script is gone blocks every prompt of that session:
        # the inert stand-in keeps that command harmless.
        Copy-Item -LiteralPath $retired -Destination $artifact -Force
      } else {
        Remove-Item -LiteralPath $artifact -Force
      }
    }
  }
  # The rollback generation, a stranded stage and the health record belong to
  # the installer and mean nothing once the hook itself is gone.
  foreach ($leftover in @("$artifact.previous", "$artifact.staged", (Join-Path $h ".saipen\health\$hostId.json"))) {
    if ((Test-Path -LiteralPath $leftover -PathType Leaf) -and -not (Test-Link $leftover)) {
      Remove-Item -LiteralPath $leftover -Force
    }
  }
  return $removed
}

function Remove-ArtifactNative([string]$path, [string]$source) {
  # `install_ownership.py remove-artifact`: an unchanged guard goes, a file its
  # owner modified stays.
  if (Test-Link $path) { throw "hook artifact is a link: $path" }
  if ((Get-FileSha256 $path) -ne (Get-FileSha256 $source)) { return $false }
  Remove-Item -LiteralPath $path -Force
  return $true
}

function Remove-Hooks {
  # Hook surfaces come from the ONE adapter registry, never a second
  # handwritten host inventory. It removes both the current install surface and
  # every registry-declared legacy surface -- including the singular `plugin/`
  # copy the supported runtime would otherwise load a second time.
  $registryPath = Join-Path (Split-Path $PSScriptRoot) "extensions\adapters\registry.json"
  if (-not (Test-Path $registryPath)) { return "adapter registry missing: $registryPath" }
  try {
    $registry = Get-Content -LiteralPath $registryPath -Raw -Encoding utf8 | ConvertFrom-Json
  } catch {
    return "adapter registry read FAILED: $($_.Exception.Message)"
  }
  $surfaces = @()
  $entries = 0
  foreach ($adapter in @($registry.adapters)) {
    if ($adapter.PSObject.Properties.Name -contains "hook_installer" -and $adapter.hook_installer) {
      if (-not $script:Python) {
        try {
          $entries += Remove-HookNative $adapter
        } catch {
          return "native hook remove FAILED ($($adapter.id)): $($_.Exception.Message)"
        }
        continue
      }
      $result = & $script:Python -B (Get-NativePath (Join-Path (Split-Path $PSScriptRoot) ([string]$adapter.hook_installer))) ([string]$adapter.id) --home $h --uninstall 2>&1
      if ($LASTEXITCODE -ne 0) { return "native hook remove FAILED: $result" }
      continue
    }
    if ($adapter.PSObject.Properties.Name -contains "install" -and $adapter.install) {
      if ($adapter.install.PSObject.Properties.Name -contains "hook" -and $adapter.install.hook) {
        $surfaces += @{ path = [string]$adapter.install.hook; source = [string]$adapter.hook_artifact }
      }
    }
    if ($adapter.PSObject.Properties.Name -contains "legacy_hook_surfaces") {
      foreach ($surface in @($adapter.legacy_hook_surfaces)) {
        if ($surface) { $surfaces += @{ path = [string]$surface; source = [string]$adapter.hook_artifact } }
      }
    }
  }
  $removed = 0
  foreach ($surface in $surfaces) {
    $path = $surface.path.Replace("~", $h)
    if (-not (Test-Path $path -PathType Leaf)) { continue }
    try {
      $source = Get-NativePath (Join-Path (Split-Path $PSScriptRoot) $surface.source)
      if (-not $script:Python) {
        if (Remove-ArtifactNative (Get-NativePath $path) $source) { $removed++ }
        continue
      }
      $result = & $script:Python -B (Join-Path $PSScriptRoot "install_ownership.py") remove-artifact (Get-NativePath $path) --source $source --home $h 2>&1
      if ($LASTEXITCODE -ne 0) { throw "hook ownership cleanup: $result" }
      $removed++
    } catch {
      return "hook remove FAILED ($path): $($_.Exception.Message)"
    }
  }
  if (-not $script:Python -and ($removed + $entries) -gt 0) {
    return "guard hook removed natively ($entries config entries, $removed plugin files)"
  }
  if ($removed -gt 0) { return "guard hook removed" }
  return "clean"
}

function Report([string]$label, [string]$result) {
  "{0,-28} {1}" -f $label, $result
  if ($result -match "FAILED") { $script:BootstrapFailed = $true }
}

Write-Host "saipen uninstaller"
if (-not $script:Python) {
  Write-Host "No working Python interpreter: removing natively, by the same ownership rules."
}
Write-Host "------------------------------------------------------------"
Report "Claude Code skill" (Remove-Skill (Resolve-HostSurface '~/.claude/skills/saipen'))
Report "Claude Code CLAUDE.md" (Remove-Block (Resolve-HostSurface '~/.claude/CLAUDE.md'))
Report "OpenCode skill" (Remove-Skill "$h\.config\opencode\skills\saipen")
Report "OpenCode AGENTS.md" (Remove-Block "$h\.config\opencode\AGENTS.md")
Report "guard hooks" (Remove-Hooks)
Report "Codex skill" (Remove-Skill "$h\.codex\skills\saipen")
Report "Codex AGENTS.md" (Remove-Block "$h\.codex\AGENTS.md")
# ZAICODE keeps its own isolated HOME, named by ZAICODE_HOME (registry).
if (-not [string]::IsNullOrWhiteSpace($env:ZAICODE_HOME)) {
  Report "ZAICODE skill" (Remove-Skill "$env:ZAICODE_HOME\.zcode\skills\saipen")
  Report "ZAICODE AGENTS.md" (Remove-Block "$env:ZAICODE_HOME\.zcode\AGENTS.md")
}
Report "Gemini GEMINI.md" (Remove-Block "$h\.gemini\GEMINI.md")
Report "~/.agents skills" (Remove-Skill "$h\.agents\skills\saipen")
Report "FreeBuff knowledge" (Remove-Block "$h\.knowledge.md")
Report "FreeBuff AGENTS.md" (Remove-Block "$h\.AGENTS.md")
$plugRoot = "$h\.gemini\config\plugins"
if (Test-Path $plugRoot) {
  Get-ChildItem $plugRoot -Directory | ForEach-Object {
    $skillsPath = Join-Path $_.FullName "skills\saipen"
    Report "Antigravity [$($_.Name)]" (Remove-Skill $skillsPath)
  }
}
Report "Aider conf" (Remove-Aider "$h\.aider.conf.yml")
Report "PATH launcher" (Remove-PathLauncher $h)
Report "scheduled inject task" (Remove-Task)
Write-Host "------------------------------------------------------------"
if ($script:BootstrapFailed) {
  Write-Host "FAILED. Fix reported errors and re-run." -ForegroundColor Red
  exit 1
}
Write-Host "Done. SAIPEN global hooks removed."

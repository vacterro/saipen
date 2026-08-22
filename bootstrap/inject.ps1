# saipen injector -- installs saipen as default protocol on every agentic system found.
# Run from the clone dir:  powershell -ExecutionPolicy Bypass -File .\inject.ps1
# Idempotent: safe to re-run any time (skips what's already installed).

param([string]$SkillHome = (Join-Path (Split-Path $PSScriptRoot) "saipen"))

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
# Raw .NET File APIs take the path as a plain string, and on Unix a
# backslash is a legal filename character, not a directory separator --
# PowerShell cmdlets (Test-Path, Copy-Item) normalize the Windows-style
# paths below, but [System.IO.File] does not, so every raw .NET call gets
# the platform-native spelling.
function Get-NativePath([string]$path) {
  return $path.Replace('\', [System.IO.Path]::DirectorySeparatorChar)
}
function Write-NoBom([string]$file, [string]$text) {
  if ((Test-Path $file) -and -not (Test-Path "$file.bak")) { Copy-Item $file "$file.bak" -Force }
  [System.IO.File]::WriteAllText((Get-NativePath $file), $text, $Utf8NoBom)
}
try { $SkillHome = (Resolve-Path $SkillHome).Path } catch {
  Write-Host "FATAL: saipen folder not found at $SkillHome" -ForegroundColor Red; exit 1
}
# BOOT.md, not RFC.md: the sanity check must name the file the injected block
# actually sends agents to. RFC.md has been a redirect stub since the v7.190.0
# split, so a clone missing BOOT.md but carrying the stub would pass this guard
# and install an entry point with no rules behind it.
if (-not (Test-Path (Join-Path $SkillHome "BOOT.md"))) {
  Write-Host "FATAL: BOOT.md missing in $SkillHome" -ForegroundColor Red; exit 1
}
$Root = Split-Path $SkillHome
$ManifestPath = Join-Path $SkillHome "MANIFEST.json"
try {
  $RuntimeManifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
} catch {
  Write-Host "FATAL: runtime manifest unreadable at $ManifestPath`: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
function Get-InstallRelativePath([string]$sourcePath) {
  $normalized = $sourcePath.Replace('\', '/')
  if ([string]::IsNullOrWhiteSpace($normalized) -or
      $normalized.StartsWith('/') -or
      $normalized -match '^[A-Za-z]:' -or
      $normalized -match '(^|/)\.\.(/|$)') {
    throw "unsafe runtime manifest path: $sourcePath"
  }
  if ($normalized.StartsWith('saipen/')) { $normalized = $normalized.Substring(7) }
  return $normalized.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
}

function Get-SourcePath([string]$sourcePath) {
  $normalized = $sourcePath.Replace('\', '/')
  if ([string]::IsNullOrWhiteSpace($normalized) -or
      $normalized.StartsWith('/') -or
      $normalized -match '^[A-Za-z]:' -or
      $normalized -match '(^|/)\.\.(/|$)') {
    throw "unsafe runtime manifest source: $sourcePath"
  }
  $native = $normalized.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
  $candidate = [System.IO.Path]::GetFullPath((Join-Path $Root $native))
  $rootPrefix = [System.IO.Path]::GetFullPath($Root).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
  $comparison = if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
    [System.StringComparison]::OrdinalIgnoreCase
  } else {
    [System.StringComparison]::Ordinal
  }
  if (-not $candidate.StartsWith($rootPrefix, $comparison)) {
    throw "runtime manifest source escapes repository root: $sourcePath"
  }
  return $candidate
}

try {
  if (@($RuntimeManifest.files).Count -eq 0 -or
      @($RuntimeManifest.copy_trees).Count -eq 0 -or
      @($RuntimeManifest.managed_dirs).Count -eq 0 -or
      @($RuntimeManifest.phase_docs.files).Count -eq 0) {
    throw "runtime manifest lacks nonempty files/copy_trees/managed_dirs/phase_docs.files"
  }
  foreach ($rel in @($RuntimeManifest.managed_dirs)) {
    if ($rel -isnot [string]) { throw "managed_dirs entries must be strings" }
    [void](Get-InstallRelativePath $rel)
  }
  foreach ($tree in @($RuntimeManifest.copy_trees)) {
    $names = @($tree.PSObject.Properties.Name)
    if ($names -notcontains "src" -or $names -notcontains "dst" -or
        $tree.src -isnot [string] -or $tree.dst -isnot [string]) {
      throw "copy_trees entries require string src/dst"
    }
    [void](Get-SourcePath $tree.src)
    [void](Get-InstallRelativePath $tree.dst)
  }
  $requiredCount = 0
  foreach ($entry in @($RuntimeManifest.files)) {
    $names = @($entry.PSObject.Properties.Name)
    if ($names -notcontains "src" -or $names -notcontains "required" -or
        $entry.src -isnot [string] -or $entry.required -isnot [bool]) {
      throw "files entries require string src and boolean required"
    }
    [void](Get-SourcePath $entry.src)
    [void](Get-InstallRelativePath $entry.src)
    if ($entry.required) { $requiredCount++ }
  }
  if ($requiredCount -eq 0) { throw "runtime manifest has no required files" }
  foreach ($phase in @($RuntimeManifest.phase_docs.files)) {
    if ($phase -isnot [string]) { throw "phase_docs.files entries must be strings" }
    [void](Get-InstallRelativePath "phases/$phase")
  }
} catch {
  Write-Host "FATAL: runtime manifest invalid: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}

$blockCore = @"
<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
SHORTCUT ACTIVATION GATE: a whole-message token that is a declared SAIPEN
shortcut (sc, cc, ccc, gg, hh, ss, sss, dd, aa, qq, qqq, ee, eee, pp, tt, or
a Cyrillic twin) is a COMMAND, never a greeting and never a style token. It
MUST activate SAIPEN and resolve through CORE.md 1.10's shortcut table BEFORE
any conversational acknowledgement, style-mode interpretation, or remembered
expansion. `sc` is `saipen crew`, never "stop caveman". A shortcut inside a
compound instruction (`saipen push + build ccc`) resolves identically as one
ordered segment. Style commands (`stop caveman`/`normal mode`) stay legal, but
a full-token shortcut match ALWAYS wins over style interpretation.
FIRST-OUTPUT LANGUAGE GATE: when project root contains .saipen/, SAIPEN is
active for the entire session including ordinary Q&A. BEFORE composing ANY
assistant response (acknowledgement, explanation, or tool preamble), read
STYLE.md and resolve its single reply_language: value. A pinned value (et,
en, or ru) is the absolute chat language for EVERY response including the
first, and incoming user language MUST NOT override it. Language detection
precedence applies ONLY when reply_language is auto. Missing, duplicated,
invalid, or unreadable STYLE language authority is a deterministic
bootstrap/style failure -- never guess a language and emit substantive output.
On "saipen set" / "saipen ..." commands, or when project root contains
.saipen/: read $SkillHome\BOOT.md (cold-start kernel) + $SkillHome\STYLE.md
and follow them. BOOT.md routes on to INDEX.md, and to CORE.md when a rule
question comes up. RFC.md is a redirect stub - it holds no rules.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on "stop caveman"/"normal mode".
Memory: .saipen/ at project root - read .saipen/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/saipen.
Crew: a bare subSaipen name (saihunt/saipython/saiwiki) = adopt that role and
start working (extensions/subs/crew.md); saipen crew = the serial
full-platoon convergence circuit (never a window layout).
UI work: also obey $SkillHome\UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->
"@
$blockCore = $blockCore.Trim([char[]]"`r`n")

function Get-Newline([string]$text) {
  if ($text.Contains("`r`n")) { return "`r`n" }
  return "`n"
}

function Get-BlockCore([string]$text) {
  $nl = Get-Newline $text
  return ($blockCore -replace "`r?`n", $nl)
}

function Add-Block([string]$file) {
  if (Test-Path $file) {
    if (-not (Test-Path $file -PathType Leaf)) { throw "config path is not a file: $file" }
    $text = [System.IO.File]::ReadAllText((Get-NativePath $file))
    $match = [regex]::Match($text, '(?s)<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->')
    $core = Get-BlockCore $text
    if ($match.Success) {
      $existing = $match.Value -replace "`r`n", "`n"
      $canonical = $blockCore -replace "`r`n", "`n"
      if ($existing -eq $canonical) { return "already" }
      $clean = $text.Substring(0, $match.Index) + $core + $text.Substring($match.Index + $match.Length)
      Write-NoBom $file $clean
      return "block refreshed"
    }
    $nl = Get-Newline $text
    Write-NoBom $file ($text + $nl + $core + $nl)
    return "block added"
  }
  $dir = Split-Path $file
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir -ErrorAction Stop | Out-Null }
  Write-NoBom $file ($blockCore + "`n")
  return "file created"
}

function Copy-Skill([string]$dst) {
  # MANIFEST.json owns every copied file/tree and replaced destination. Any
  # copy failure surfaces -- a claimed "copied" over a half-copy is exactly
  # the silent-failure class hunt.md exists to catch.
  if ([string]::IsNullOrWhiteSpace($dst)) { return "copy FAILED ($dst): unsafe destination" }
  $stage = $null
  $backup = $null
  try {
    $parent = Split-Path $dst
    if ([string]::IsNullOrWhiteSpace($parent)) { throw "unsafe destination parent" }
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force $parent -ErrorAction Stop | Out-Null }
    $leaf = Split-Path $dst -Leaf
    $stage = Join-Path $parent ".$leaf.saipen-stage-$PID"
    $backup = Join-Path $parent ".$leaf.saipen-backup-$PID"
    if ((Test-Path $stage) -or (Test-Path $backup)) {
      throw "stale staging/backup path exists; inspect before retry"
    }
    New-Item -ItemType Directory $stage -ErrorAction Stop | Out-Null
    foreach ($rel in $RuntimeManifest.managed_dirs) {
      [void](Get-InstallRelativePath ([string]$rel))
    }
    foreach ($tree in $RuntimeManifest.copy_trees) {
      $source = Get-SourcePath ([string]$tree.src)
      $target = Join-Path $stage (Get-InstallRelativePath ([string]$tree.dst))
      if (-not (Test-Path $source -PathType Container)) { throw "runtime manifest tree missing: $($tree.src)" }
      if (((Get-Item -LiteralPath $source -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "runtime manifest tree is a reparse point: $($tree.src)"
      }
      $reparse = Get-ChildItem -LiteralPath $source -Recurse -Force -ErrorAction Stop |
        Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 }
      if ($reparse) { throw "runtime manifest tree contains reparse point: $($reparse[0].FullName)" }
      New-Item -ItemType Directory -Force $target -ErrorAction Stop | Out-Null
      Get-ChildItem -LiteralPath $source -Force -ErrorAction Stop |
        Copy-Item -Destination $target -Recurse -Force -ErrorAction Stop
    }
    foreach ($entry in @($RuntimeManifest.files | Where-Object { $_.required -eq $true })) {
      $source = Get-SourcePath ([string]$entry.src)
      $target = Join-Path $stage (Get-InstallRelativePath ([string]$entry.src))
      if (-not (Test-Path $source -PathType Leaf)) { throw "runtime manifest file missing: $($entry.src)" }
      if (((Get-Item -LiteralPath $source -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "runtime manifest file is a reparse point: $($entry.src)"
      }
      $parent = Split-Path $target
      if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force $parent -ErrorAction Stop | Out-Null }
      Copy-Item -LiteralPath $source -Destination $target -Force -ErrorAction Stop
    }
    Get-ChildItem -LiteralPath $stage -Directory -Recurse -Force -ErrorAction Stop |
      Where-Object Name -eq "__pycache__" |
      Remove-Item -Recurse -Force -ErrorAction Stop
    Get-ChildItem -LiteralPath $stage -File -Recurse -Force -ErrorAction Stop |
      Where-Object Extension -in ".pyc", ".pyo" |
      Remove-Item -Force -ErrorAction Stop
    foreach ($entry in @($RuntimeManifest.files | Where-Object { $_.required -eq $true })) {
      $target = Join-Path $stage (Get-InstallRelativePath ([string]$entry.src))
      if (-not (Test-Path $target -PathType Leaf)) { throw "installed runtime file missing: $($entry.src)" }
    }
    foreach ($phase in $RuntimeManifest.phase_docs.files) {
      if (-not (Test-Path (Join-Path $stage "phases\$phase") -PathType Leaf)) {
        throw "installed phase document missing: $phase"
      }
    }
    if (Test-Path $dst) { Move-Item -LiteralPath $dst -Destination $backup -ErrorAction Stop }
    try {
      Move-Item -LiteralPath $stage -Destination $dst -ErrorAction Stop
      $stage = $null
    } catch {
      if ((Test-Path $backup) -and -not (Test-Path $dst)) {
        Move-Item -LiteralPath $backup -Destination $dst -ErrorAction SilentlyContinue
      }
      throw
    }
    if (Test-Path $backup) { Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction Stop }
    $backup = $null
    return "copied (re-run after updates)"
  } catch {
    if ($stage -and (Test-Path $stage)) {
      Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    }
    if ($backup -and (Test-Path $backup) -and -not (Test-Path $dst)) {
      Move-Item -LiteralPath $backup -Destination $dst -ErrorAction SilentlyContinue
    }
    return "copy FAILED ($dst): $($_.Exception.Message)"
  }
}

$h = $env:USERPROFILE
$report = New-Object System.Collections.ArrayList

# --- Claude Code ---
if (Test-Path "$h\.claude") {
  [void]$report.Add(@("Claude Code skill",     (Copy-Skill "$h\.claude\skills\saipen")))
  [void]$report.Add(@("Claude Code CLAUDE.md", (Add-Block  "$h\.claude\CLAUDE.md")))
} else { [void]$report.Add(@("Claude Code", "not installed - skip")) }

# --- OpenCode ---
if (Test-Path "$h\.config\opencode") {
  [void]$report.Add(@("OpenCode skill",     (Copy-Skill "$h\.config\opencode\skills\saipen")))
  [void]$report.Add(@("OpenCode AGENTS.md", (Add-Block  "$h\.config\opencode\AGENTS.md")))
} else { [void]$report.Add(@("OpenCode", "not installed - skip")) }

# --- Codex CLI ---
if (Test-Path "$h\.codex") {
  [void]$report.Add(@("Codex skill",     (Copy-Skill "$h\.codex\skills\saipen")))
  [void]$report.Add(@("Codex AGENTS.md", (Add-Block  "$h\.codex\AGENTS.md")))
} else { [void]$report.Add(@("Codex", "not installed - skip")) }

# --- Gemini CLI ---
if (Test-Path "$h\.gemini") {
  [void]$report.Add(@("Gemini GEMINI.md", (Add-Block "$h\.gemini\GEMINI.md")))
} else { [void]$report.Add(@("Gemini", "not installed - skip")) }

# --- Generic ~/.agents/skills (FreeBuff etc.) ---
# Copy, lowercase: these readers skip junctions and uppercase dirs.
if (Test-Path "$h\.agents\skills") {
  [void]$report.Add(@("~/.agents skills", (Copy-Skill "$h\.agents\skills\saipen")))
} else { [void]$report.Add(@("~/.agents", "not installed - skip")) }

# --- Antigravity plugins (copy: IDE locks dirs, junction impossible while open) ---
$plugRoot = "$h\.gemini\config\plugins"
if (Test-Path $plugRoot) {
  Get-ChildItem $plugRoot -Directory | ForEach-Object {
    $skillsDir = Join-Path $_.FullName "skills"
    if (Test-Path $skillsDir) {
      [void]$report.Add(@("Antigravity [$($_.Name)]", (Copy-Skill (Join-Path $skillsDir "saipen"))))
    }
  }
}

# --- Aider (boot set is BOOT.md + STYLE.md, same promise as every platform) ---
$aider = "$h\.aider.conf.yml"
$skillPath = Join-Path $SkillHome "BOOT.md"
$stylePath = Join-Path $SkillHome "STYLE.md"
if (Get-Command aider -ErrorAction SilentlyContinue) {
  if (Test-Path $aider) {
    $conf = Get-Content $aider -Raw -Encoding utf8
    if (($conf -match [regex]::Escape($skillPath)) -and ($conf -match [regex]::Escape($stylePath))) {
      [void]$report.Add(@("Aider conf", "already"))
    } elseif ($conf -notmatch '(?m)^read:') {
      if (-not (Test-Path "$aider.bak")) { Copy-Item $aider "$aider.bak" -Force -ErrorAction Stop }
      $original = [System.IO.File]::ReadAllBytes((Get-NativePath $aider))
      $addition = $Utf8NoBom.GetBytes("`n# saipen protocol auto-loaded`nread:`n  - $skillPath`n  - $stylePath`n")
      $combined = New-Object byte[] ($original.Length + $addition.Length)
      [System.Buffer]::BlockCopy($original, 0, $combined, 0, $original.Length)
      [System.Buffer]::BlockCopy($addition, 0, $combined, $original.Length, $addition.Length)
      [System.IO.File]::WriteAllBytes((Get-NativePath $aider), $combined)
      [void]$report.Add(@("Aider conf", "read: appended"))
    } else {
      [void]$report.Add(@("Aider conf", "has own read: - add manually: $skillPath + $stylePath"))
    }
  } else {
    Write-NoBom $aider "# saipen protocol auto-loaded`nread:`n  - $skillPath`n  - $stylePath`n"
    [void]$report.Add(@("Aider conf", "created"))
  }
} else { [void]$report.Add(@("Aider", "not installed - skip")) }

# --- Report ---
Write-Host ""
Write-Host "saipen injector report (source: $SkillHome)" -ForegroundColor Yellow
Write-Host ("-" * 60)
foreach ($r in $report) {
  $color = if ($r[1] -match "FAILED|manually") { "Red" }
           elseif ($r[1] -match "already|skip") { "DarkGray" } else { "Green" }
  Write-Host ("{0,-28} {1}" -f $r[0], $r[1]) -ForegroundColor $color
}
Write-Host ("-" * 60)
$failed = @($report | Where-Object { $_[1] -match "FAILED" })
if ($failed.Count -gt 0) {
  Write-Host "FAILED. Fix reported errors and re-run." -ForegroundColor Red
  exit 1
}
Write-Host "Done. Test: open any project in any agent, say: saipen set" -ForegroundColor Yellow

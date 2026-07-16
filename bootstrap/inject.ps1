# asp injector вЂ” installs asp as default protocol on every agentic system found.
# Run from the clone dir:  powershell -ExecutionPolicy Bypass -File .\inject.ps1
# Idempotent: safe to re-run any time (skips what's already installed).
# Also migrates pre-3.0 installs named "VAC".

param([string]$SkillHome = (Join-Path $PSScriptRoot "vacskill"))

$ErrorActionPreference = "Continue"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-NoBom([string]$file, [string]$text) {
  [System.IO.File]::WriteAllText($file, $text, $Utf8NoBom)
}
try { $SkillHome = (Resolve-Path $SkillHome).Path } catch {
  Write-Host "FATAL: asp folder not found at $SkillHome" -ForegroundColor Red; exit 1
}
if (-not (Test-Path (Join-Path $SkillHome "PROTOCOL.md"))) {
  Write-Host "FATAL: PROTOCOL.md missing in $SkillHome" -ForegroundColor Red; exit 1
}

$block = @"

<!-- VACSKILL:BEGIN -->
## asp protocol (global)
On "asp SET" / "asp ..." (short alias "vac ...") commands, or when
project root contains .asp/: read $SkillHome\PROTOCOL.md + $SkillHome\STYLE.md
and follow them.
Memory: .asp/ at project root - read .asp/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/vacskill.
UI work: also obey $SkillHome\UI.md (Win95 dark golden, Verdana, no AA).
<!-- VACSKILL:END -->
"@

# Strip a pre-3.0 <!-- VAC:BEGIN -->..<!-- VAC:END --> block: it points at the
# old VAC\ folder, which no longer exists.
function Remove-LegacyBlock([string]$file) {
  if (-not (Test-Path $file)) { return $false }
  $text = Get-Content $file -Raw -Encoding utf8
  if ($text -notmatch '<!-- VAC:BEGIN -->') { return $false }
  $clean = [regex]::Replace($text, '(?s)\s*<!-- VAC:BEGIN -->.*?<!-- VAC:END -->\s*', "`n")
  Write-NoBom $file ($clean.TrimEnd() + "`n")
  return $true
}

function Add-Block([string]$file) {
  $migrated = Remove-LegacyBlock $file
  if (Test-Path $file) {
    if (Select-String -Path $file -Pattern "VACSKILL:BEGIN" -Quiet) {
      if (Select-String -Path $file -Pattern "PROTOCOL\.md" -Quiet) { return "already" }
      # 3.x block points at SKILL.md вЂ” replace with PROTOCOL.md block
      $text = Get-Content $file -Raw -Encoding utf8
      $clean = [regex]::Replace($text, '(?s)\s*<!-- VACSKILL:BEGIN -->.*?<!-- VACSKILL:END -->\s*', "`n")
      Write-NoBom $file ($clean.TrimEnd() + $block + "`n")
      return "block upgraded to PROTOCOL.md"
    }
    $text = Get-Content $file -Raw -Encoding utf8
    Write-NoBom $file ($text.TrimEnd() + $block + "`n")
    return $(if ($migrated) { "migrated from VAC" } else { "block added" })
  }
  $dir = Split-Path $file
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Write-NoBom $file ($block.TrimStart() + "`n")
  return "file created"
}

# Drop a pre-3.0 skill dir. Junctions are unlinked; real dirs deleted only when
# they are ours (SKILL.md with asp/VAC frontmatter inside).
function Remove-LegacySkill([string]$path) {
  if (-not (Test-Path $path)) { return $false }
  $item = Get-Item $path -Force
  if ($item.LinkType) { cmd /c rmdir "$path" | Out-Null; return $true }
  $marker = Join-Path $path "SKILL.md"
  if (Test-Path $marker) {
    if (Select-String -Path $marker -Pattern "^name:\s*(VAC|vacskill)\s*$" -Quiet) {
      Remove-Item -Recurse -Force $path; return $true
    }
  }
  return $false
}

function Add-Junction([string]$target, [string]$legacy) {
  if ($legacy) { Remove-LegacySkill $legacy | Out-Null }
  if (Test-Path (Join-Path $target "SKILL.md")) {
    $item = Get-Item $target -Force
    if ($item.LinkType) { return "already" }
    Remove-LegacySkill $target | Out-Null   # stale copy -> replace with junction
  }
  if (Test-Path $target) { return "exists but not asp - check manually" }
  $parent = Split-Path $target
  if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force $parent | Out-Null }
  cmd /c mklink /J "$target" "$SkillHome" | Out-Null
  if (Test-Path (Join-Path $target "SKILL.md")) { return "junction created" }
  return "FAILED"
}

function Copy-Skill([string]$dst, [string]$legacy) {
  if ($legacy) { Remove-LegacySkill $legacy | Out-Null }
  if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force $dst | Out-Null }
  Copy-Item (Join-Path $SkillHome "SKILL.md"),(Join-Path $SkillHome "PROTOCOL.md"),(Join-Path $SkillHome "UI.md"),(Join-Path $SkillHome "STYLE.md") $dst -Force
}

$h = $env:USERPROFILE
$report = New-Object System.Collections.ArrayList

# --- Claude Code ---
if (Test-Path "$h\.claude") {
  [void]$report.Add(@("Claude Code skill",     (Add-Junction "$h\.claude\skills\vacskill" "$h\.claude\skills\VAC")))
  [void]$report.Add(@("Claude Code CLAUDE.md", (Add-Block    "$h\.claude\CLAUDE.md")))
} else { [void]$report.Add(@("Claude Code", "not installed - skip")) }

# --- OpenCode ---
if (Test-Path "$h\.config\opencode") {
  [void]$report.Add(@("OpenCode skill",     (Add-Junction "$h\.config\opencode\skills\vacskill" "$h\.config\opencode\skills\vac")))
  [void]$report.Add(@("OpenCode AGENTS.md", (Add-Block    "$h\.config\opencode\AGENTS.md")))
} else { [void]$report.Add(@("OpenCode", "not installed - skip")) }

# --- Codex CLI ---
if (Test-Path "$h\.codex") {
  [void]$report.Add(@("Codex skill",     (Add-Junction "$h\.codex\skills\vacskill" "$h\.codex\skills\vac")))
  [void]$report.Add(@("Codex AGENTS.md", (Add-Block    "$h\.codex\AGENTS.md")))
} else { [void]$report.Add(@("Codex", "not installed - skip")) }

# --- Gemini CLI ---
if (Test-Path "$h\.gemini") {
  [void]$report.Add(@("Gemini GEMINI.md", (Add-Block "$h\.gemini\GEMINI.md")))
} else { [void]$report.Add(@("Gemini", "not installed - skip")) }

# --- Generic ~/.agents/skills (FreeBuff etc.) ---
# Copy, lowercase: these readers skip junctions and uppercase dirs.
if (Test-Path "$h\.agents\skills") {
  Remove-LegacySkill "$h\.agents\skills\VAC" | Out-Null
  Copy-Skill "$h\.agents\skills\vacskill" "$h\.agents\skills\vac"
  [void]$report.Add(@("~/.agents skills", "copied (re-run after updates)"))
} else { [void]$report.Add(@("~/.agents", "not installed - skip")) }

# --- Antigravity plugins (copy: IDE locks dirs, junction impossible while open) ---
$plugRoot = "$h\.gemini\config\plugins"
if (Test-Path $plugRoot) {
  Get-ChildItem $plugRoot -Directory | ForEach-Object {
    $skillsDir = Join-Path $_.FullName "skills"
    if (Test-Path $skillsDir) {
      Copy-Skill (Join-Path $skillsDir "vacskill") (Join-Path $skillsDir "VAC")
      [void]$report.Add(@("Antigravity [$($_.Name)]", "copied (re-run after updates)"))
    }
  }
}

# --- Aider ---
$aider = "$h\.aider.conf.yml"
$skillPath = Join-Path $SkillHome "PROTOCOL.md"
if (Get-Command aider -ErrorAction SilentlyContinue) {
  if (Test-Path $aider) {
    $conf = Get-Content $aider -Raw -Encoding utf8
    if ($conf -match '[\\/](VAC|vacskill)[\\/]SKILL\.md') {   # pre-4.0 path -> repoint
      Write-NoBom $aider ($conf -replace '.*[\\/](VAC|vacskill)[\\/]SKILL\.md', "  - $skillPath")
      [void]$report.Add(@("Aider conf", "migrated to PROTOCOL.md"))
    } elseif ($conf -match [regex]::Escape($skillPath)) {
      [void]$report.Add(@("Aider conf", "already"))
    } elseif ($conf -notmatch '(?m)^read:') {
      Write-NoBom $aider ($conf.TrimEnd() + "`n`n# asp protocol auto-loaded`nread:`n  - $skillPath`n")
      [void]$report.Add(@("Aider conf", "read: appended"))
    } else {
      [void]$report.Add(@("Aider conf", "has own read: - add manually: $skillPath"))
    }
  } else {
    Write-NoBom $aider "# asp protocol auto-loaded`nread:`n  - $skillPath`n"
    [void]$report.Add(@("Aider conf", "created"))
  }
} else { [void]$report.Add(@("Aider", "not installed - skip")) }

# --- Report ---
Write-Host ""
Write-Host "asp injector report (source: $SkillHome)" -ForegroundColor Yellow
Write-Host ("-" * 60)
foreach ($r in $report) {
  $color = if ($r[1] -match "FAILED|manually") { "Red" }
           elseif ($r[1] -match "already|skip") { "DarkGray" } else { "Green" }
  Write-Host ("{0,-28} {1}" -f $r[0], $r[1]) -ForegroundColor $color
}
Write-Host ("-" * 60)
Write-Host "Done. Test: open any project in any agent, say: asp SET" -ForegroundColor Yellow

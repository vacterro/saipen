# saipen injector -- installs saipen as default protocol on every agentic system found.
# Run from the clone dir:  powershell -ExecutionPolicy Bypass -File .\inject.ps1
# Idempotent: safe to re-run any time (skips what's already installed).

param([string]$SkillHome = (Join-Path (Split-Path $PSScriptRoot) "saipen"))

$ErrorActionPreference = "Continue"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
function Write-NoBom([string]$file, [string]$text) {
  if ((Test-Path $file) -and -not (Test-Path "$file.bak")) { Copy-Item $file "$file.bak" -Force }
  [System.IO.File]::WriteAllText($file, $text, $Utf8NoBom)
}
try { $SkillHome = (Resolve-Path $SkillHome).Path } catch {
  Write-Host "FATAL: saipen folder not found at $SkillHome" -ForegroundColor Red; exit 1
}
if (-not (Test-Path (Join-Path $SkillHome "RFC.md"))) {
  Write-Host "FATAL: RFC.md missing in $SkillHome" -ForegroundColor Red; exit 1
}

$block = @"

<!-- SAIPEN:BEGIN -->
## saipen protocol (global)
On "saipen set" / "saipen ..." commands, or when project root contains
.saipen/: read $SkillHome\RFC.md + $SkillHome\STYLE.md and follow them.
Chat tone: caveman-ded (STYLE.md) - compressed + blunt, on by default,
off only on "stop caveman"/"normal mode".
Memory: .saipen/ at project root - read .saipen/STATE.md before work;
checkpoint BOARD + STATE after every ticket, LOG line after every run.
Path missing (new machine)? clone github.com/vacterro/saipen.
UI work: also obey $SkillHome\UI.md (Win95 dark golden, Verdana, no AA).
<!-- SAIPEN:END -->
"@

function Add-Block([string]$file) {
  if (Test-Path $file) {
    $text = Get-Content $file -Raw -Encoding utf8
    if ($text -match '(?s)<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->') {
      $existing = $Matches[0]
      if ($existing.Trim() -eq $block.Trim()) { return "already" }
      $clean = [regex]::Replace($text, '(?s)\s*<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->\s*', "`n")
      Write-NoBom $file ($clean.TrimEnd() + $block + "`n")
      return "block refreshed"
    }
    Write-NoBom $file ($text.TrimEnd() + $block + "`n")
    return "block added"
  }
  $dir = Split-Path $file
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Write-NoBom $file ($block.TrimStart() + "`n")
  return "file created"
}

function Copy-Skill([string]$dst) {
  if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force $dst | Out-Null }
  Copy-Item (Join-Path $SkillHome "SKILL.md"),(Join-Path $SkillHome "RFC.md"),(Join-Path $SkillHome "UI.md"),(Join-Path $SkillHome "STYLE.md") $dst -Force
  Copy-Item (Join-Path $SkillHome "phases") $dst -Recurse -Force
  # validate.py resolves the schema relative to itself (../extensions/schemas),
  # so both must travel together for the skill copy to validate standalone.
  # templates/ makes init.md's "copy, do NOT freehand" reachable; tests/ makes
  # validate.md's no-Python shell fallback reachable.
  $root = Split-Path $SkillHome
  Copy-Item (Join-Path $root "tools") $dst -Recurse -Force
  New-Item -ItemType Directory -Force (Join-Path $dst "extensions") | Out-Null
  Copy-Item (Join-Path $root "extensions\schemas") (Join-Path $dst "extensions") -Recurse -Force
  Copy-Item (Join-Path $root "extensions\templates") (Join-Path $dst "extensions") -Recurse -Force
  New-Item -ItemType Directory -Force (Join-Path $dst "tests") | Out-Null
  Copy-Item (Join-Path $root "tests\validate.sh"),(Join-Path $root "tests\validate.ps1") (Join-Path $dst "tests") -Force
  return "copied (re-run after updates)"
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

# --- Aider (boot set is RFC.md + STYLE.md, same promise as every platform) ---
$aider = "$h\.aider.conf.yml"
$skillPath = Join-Path $SkillHome "RFC.md"
$stylePath = Join-Path $SkillHome "STYLE.md"
if (Get-Command aider -ErrorAction SilentlyContinue) {
  if (Test-Path $aider) {
    $conf = Get-Content $aider -Raw -Encoding utf8
    if (($conf -match [regex]::Escape($skillPath)) -and ($conf -match [regex]::Escape($stylePath))) {
      [void]$report.Add(@("Aider conf", "already"))
    } elseif ($conf -notmatch '(?m)^read:') {
      Write-NoBom $aider ($conf.TrimEnd() + "`n`n# saipen protocol auto-loaded`nread:`n  - $skillPath`n  - $stylePath`n")
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
Write-Host "Done. Test: open any project in any agent, say: saipen set" -ForegroundColor Yellow

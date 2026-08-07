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

function Remove-Block([string]$file) {
  if (Test-Path $file) {
    if (-not (Test-Path $file -PathType Leaf)) { throw "config path is not a file: $file" }
    $text = [System.IO.File]::ReadAllText((Get-NativePath $file))
    $match = [regex]::Match($text, '(?s)(?:\r\n|\n)?<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->(?:\r\n|\n)?')
    if ($match.Success) {
      $clean = $text.Substring(0, $match.Index) + $text.Substring($match.Index + $match.Length)
      # Backup the file before uninstalling just in case
      Copy-Item $file "$file.uninstalled.bak" -Force -ErrorAction Stop
      [System.IO.File]::WriteAllText((Get-NativePath $file), $clean, $Utf8NoBom)
      return "block removed"
    }
  }
  return "clean"
}

function Remove-Skill([string]$path) {
  if (Test-Path $path) {
    try {
      Remove-Item -Recurse -Force $path -ErrorAction Stop
      return "skill removed"
    } catch {
      return "remove FAILED ($path): $($_.Exception.Message)"
    }
  }
  return "clean"
}

function Remove-Task() {
  # Remove the auto-scheduled inject task (T-531) when uninstalling, so a
  # de-advertised protocol does not keep pulling + injecting every 15 minutes.
  $t = Get-ScheduledTask -TaskName "saipen-inject" -ErrorAction SilentlyContinue
  if ($t) {
    schtasks /Delete /TN "saipen-inject" /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return "task removed" }
    return "task remove FAILED (schtasks rc $LASTEXITCODE)"
  }
  return "clean"
}

function Remove-Aider([string]$file) {
  # Remove exactly the block the injector wrote (comment + read: key +
  # consecutive saipen RFC/STYLE items), CRLF-tolerant -- never any other
  # read: line the user owns.
  if (Test-Path $file) {
    if (-not (Test-Path $file -PathType Leaf)) { throw "config path is not a file: $file" }
    $text = [System.IO.File]::ReadAllText((Get-NativePath $file))
    $blockRe = '(?m)(?:\r?\n)?# saipen protocol auto-loaded\r?\nread:\r?\n(?:[ \t]*-[ \t].*saipen[\\/](?:RFC|STYLE)\.md\r?\n?)+'
    if ($text -match $blockRe) {
      $clean = [regex]::Replace($text, $blockRe, "")
      Copy-Item $file "$file.uninstalled.bak" -Force -ErrorAction Stop
      [System.IO.File]::WriteAllText((Get-NativePath $file), $clean, $Utf8NoBom)
      return "aider conf cleaned"
    } elseif ($text -match 'saipen[\\/]RFC\.md') {
      return "manual aider conf (please remove manually)"
    }
  }
  return "clean"
}

$h = $env:USERPROFILE
$script:BootstrapFailed = $false
function Report([string]$label, [string]$result) {
  "{0,-28} {1}" -f $label, $result
  if ($result -match "FAILED") { $script:BootstrapFailed = $true }
}

Write-Host "saipen uninstaller"
Write-Host "------------------------------------------------------------"
Report "Claude Code skill" (Remove-Skill "$h\.claude\skills\saipen")
Report "Claude Code CLAUDE.md" (Remove-Block "$h\.claude\CLAUDE.md")
Report "OpenCode skill" (Remove-Skill "$h\.config\opencode\skills\saipen")
Report "OpenCode AGENTS.md" (Remove-Block "$h\.config\opencode\AGENTS.md")
Report "Codex skill" (Remove-Skill "$h\.codex\skills\saipen")
Report "Codex AGENTS.md" (Remove-Block "$h\.codex\AGENTS.md")
Report "Gemini GEMINI.md" (Remove-Block "$h\.gemini\GEMINI.md")
Report "~/.agents skills" (Remove-Skill "$h\.agents\skills\saipen")
$plugRoot = "$h\.gemini\config\plugins"
if (Test-Path $plugRoot) {
  Get-ChildItem $plugRoot -Directory | ForEach-Object {
    $skillsPath = Join-Path $_.FullName "skills\saipen"
    Report "Antigravity [$($_.Name)]" (Remove-Skill $skillsPath)
  }
}
Report "Aider conf" (Remove-Aider "$h\.aider.conf.yml")
Report "scheduled inject task" (Remove-Task)
Write-Host "------------------------------------------------------------"
if ($script:BootstrapFailed) {
  Write-Host "FAILED. Fix reported errors and re-run." -ForegroundColor Red
  exit 1
}
Write-Host "Done. SAIPEN global hooks removed."

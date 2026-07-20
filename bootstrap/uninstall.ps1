$ErrorActionPreference = "Continue"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Remove-Block([string]$file) {
  if (Test-Path $file) {
    $text = Get-Content $file -Raw -Encoding utf8
    if ($text -match '<!-- SAIPEN:BEGIN -->') {
      $clean = [regex]::Replace($text, '(?s)\s*<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->\s*', "`n")
      # Backup the file before uninstalling just in case
      Copy-Item $file "$file.uninstalled.bak" -Force
      [System.IO.File]::WriteAllText($file, $clean.TrimEnd() + "`n", $Utf8NoBom)
      return "block removed"
    }
  }
  return "clean"
}

function Remove-Skill([string]$path) {
  if (Test-Path $path) {
    Remove-Item -Recurse -Force $path
    return "skill removed"
  }
  return "clean"
}

function Remove-Aider([string]$file) {
  if (Test-Path $file) {
    $text = Get-Content $file -Raw -Encoding utf8
    if ($text -match '# saipen protocol auto-loaded\nread:\n  - .*?saipen[\\/]RFC\.md\n') {
      $clean = [regex]::Replace($text, '(?m)^# saipen protocol auto-loaded\nread:\n  - .*?saipen[\\/]RFC\.md\n', "")
      Copy-Item $file "$file.uninstalled.bak" -Force
      [System.IO.File]::WriteAllText($file, $clean, $Utf8NoBom)
      return "aider conf cleaned"
    } elseif ($text -match 'saipen[\\/]RFC\.md') {
      return "manual aider conf (please remove manually)"
    }
  }
  return "clean"
}

$h = $env:USERPROFILE
Write-Host "saipen uninstaller"
Write-Host "------------------------------------------------------------"
"{0,-28} {1}" -f "Claude Code skill", (Remove-Skill "$h\.claude\skills\saipen")
"{0,-28} {1}" -f "Claude Code CLAUDE.md", (Remove-Block "$h\.claude\CLAUDE.md")
"{0,-28} {1}" -f "OpenCode skill", (Remove-Skill "$h\.config\opencode\skills\saipen")
"{0,-28} {1}" -f "OpenCode AGENTS.md", (Remove-Block "$h\.config\opencode\AGENTS.md")
"{0,-28} {1}" -f "Codex skill", (Remove-Skill "$h\.codex\skills\saipen")
"{0,-28} {1}" -f "Codex AGENTS.md", (Remove-Block "$h\.codex\AGENTS.md")
"{0,-28} {1}" -f "Gemini GEMINI.md", (Remove-Block "$h\.gemini\GEMINI.md")
"{0,-28} {1}" -f "~/.agents skills", (Remove-Skill "$h\.agents\skills\saipen")
$plugRoot = "$h\.gemini\config\plugins"
if (Test-Path $plugRoot) {
  Get-ChildItem $plugRoot -Directory | ForEach-Object {
    $skillsPath = Join-Path $_.FullName "skills\saipen"
    "{0,-28} {1}" -f "Antigravity [$($_.Name)]", (Remove-Skill $skillsPath)
  }
}
"{0,-28} {1}" -f "Aider conf", (Remove-Aider "$h\.aider.conf.yml")
Write-Host "------------------------------------------------------------"
Write-Host "Done. SAIPEN global hooks removed."

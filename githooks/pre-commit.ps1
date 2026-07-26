# saiwiki: translation version-badge drift check (pre-commit hook, Windows)
# Install: copy to .git/hooks/pre-commit.ps1 (then set core.hooksPath or
#          configure git to use PowerShell hooks)

param()

$kitchen = ".saipen/saitranslate/kitchen"
$versionFile = "VERSION"

if (-not (Test-Path $kitchen) -or -not (Test-Path $versionFile)) {
    exit 0
}

$repoVer = (Get-Content $versionFile -Raw).Trim()
$stale = @()

Get-ChildItem $kitchen -Directory | ForEach-Object {
    $locale = $_.Name
    $readme = Join-Path $_.FullName "README_$($locale.ToUpper()).md"
    if (-not (Test-Path $readme)) { return }
    $content = Get-Content $readme -Raw
    if ($content -notmatch "\*\*v$([Regex]::Escape($repoVer))\*\*") {
        $stale += $locale
    }
}

if ($stale.Count -gt 0) {
    Write-Host "FAIL: translation README badge drift -- stale locale(s): $($stale -join ', ')"
    Write-Host "Run: python tools/validate.py"
    exit 1
}

exit 0

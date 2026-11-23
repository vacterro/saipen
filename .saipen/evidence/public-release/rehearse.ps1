# Public-release rehearsal, PowerShell transport. Mirrors rehearse.sh's
# guarantees on the path the README leads with: install -> set -> continue ->
# validate -> uninstall -> reinstall, in a throwaway HOME and project.
# Nothing here touches the maintainer's real HOME.
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [Parameter(Mandatory = $true)][string]$Scratch
)

$ErrorActionPreference = "Continue"
$script:step = 0
$script:fail = 0
$Log = Join-Path $Scratch "rehearsal.log"

function Say  { param($m) Write-Host $m; Add-Content -Path $Log -Value $m }
function Ok   { $script:step++; Say ""; Say "=== [$script:step] PASS: $($args[0]) ===" }
function Bad  { $script:fail++; Say ""; Say "!!! FAIL: $($args[0]) !!!" }
function Gate { param($code, $what) if ($code -eq 0) { Ok $what } else { Bad $what } }
function Check { param($cond, $what) if ($cond) { Ok $what } else { Bad $what } }

if (Test-Path $Scratch) { Remove-Item -Recurse -Force $Scratch }
$null = New-Item -ItemType Directory -Force -Path $Scratch
$null = New-Item -ItemType Directory -Force -Path (Join-Path $Scratch "home")
$null = New-Item -ItemType Directory -Force -Path (Join-Path $Scratch "project")
: > $Log

$SandboxHome = Join-Path $Scratch "home"
$Clone       = Join-Path $Scratch "clone"
$Project     = Join-Path $Scratch "project"

# Point every HOME-derived location at the sandbox BEFORE the installer runs.
$env:HOME                    = $SandboxHome
$env:USERPROFILE             = $SandboxHome
$env:LOCALAPPDATA            = Join-Path $SandboxHome "AppData\Local"
$env:APPDATA                 = Join-Path $SandboxHome "AppData\Roaming"
$env:XDG_CONFIG_HOME         = Join-Path $SandboxHome ".config"
$env:SAIPEN_USER_CONFIG_HOME = Join-Path $SandboxHome ".saipen-user"
$env:SAIPEN_UNINSTALL_SKIP_TASK = "1"
$env:PYTHONUTF8              = "1"
$env:PYTHONDONTWRITEBYTECODE = "1"
Remove-Item Env:\ZAICODE_HOME -ErrorAction SilentlyContinue

Say "scratch: $Scratch"
Say "HOME:    $env:HOME"

# ---------------------------------------------------------------- 1. clone
Say ""; Say "=== fresh clone ==="
git clone --quiet $Repo $Clone 2>&1 | Out-Null
Gate $LASTEXITCODE "git clone"
$tracked = (git -C $Clone ls-files | Measure-Object -Line).Lines
Say "clone: $tracked tracked files"
Check (Test-Path (Join-Path $Clone "bootstrap\inject.ps1")) "inject.ps1 present in clone"
Check (-not (Test-Path (Join-Path $Clone "bin\saipen.cmd"))) "repo ships no tracked bin/ launcher"

# ------------------------------------------------------------- 2. install
Say ""; Say "=== install ==="
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Clone "bootstrap\inject.ps1") *>> $Log
Gate $LASTEXITCODE "powershell -File bootstrap\inject.ps1"

$Skill   = Join-Path $SandboxHome ".agents\skills\saipen"
$Launch  = Join-Path $Skill "bin\saipen.cmd"
Check (Test-Path $Launch) "installed launcher at .agents\skills\saipen\bin\saipen.cmd"
if (Test-Path $Launch) {
    $body = Get-Content $Launch -Raw
    Check ($body -notmatch [regex]::Escape($Clone)) "installed launcher does not point at the clone"
    Check ($body -match [regex]::Escape($Skill)) "installed launcher points at the installed engine"
}

# A user marker the install must not touch, and a SAIPEN block it must add.
$null = New-Item -ItemType Directory -Force -Path (Join-Path $SandboxHome ".claude")
Set-Content -Path (Join-Path $SandboxHome ".claude\CLAUDE.md") -Value "my own claude notes" -NoNewline
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Clone "bootstrap\inject.ps1") *>> $Log
$claude = Get-Content (Join-Path $SandboxHome ".claude\CLAUDE.md") -Raw
Check ($claude -match "my own claude notes") "installer did not clobber a pre-existing CLAUDE.md"

# ------------------------------------------------- 3. set / continue / validate
Say ""; Say "=== saipen set / continue / validate ==="
Push-Location $Project
& $Launch set        *>> $Log; Gate $LASTEXITCODE "saipen set"
Check (Test-Path (Join-Path $Project ".saipen\STATE.md")) "set created .saipen\STATE.md"
& $Launch continue   *>> $Log; Gate $LASTEXITCODE "saipen continue"
$out = & $Launch validate 2>&1 | Out-String
Gate $LASTEXITCODE "saipen validate"
Check ($out -match "Conformance:\s*CURRENT_PASS") "validate reported PASS"
Pop-Location

# ------------------------------------------------------------ 4. uninstall
Say ""; Say "=== uninstall ==="
Set-Content -Path (Join-Path $SandboxHome ".agents\skills\saipen\USER-NOTES.md") -Value "mine" -NoNewline
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Clone "bootstrap\uninstall.ps1") *>> $Log
Gate $LASTEXITCODE "powershell -File bootstrap\uninstall.ps1"
Check (Test-Path (Join-Path $Project ".saipen\STATE.md")) "project .saipen\ memory survived uninstall"
Check (-not (Test-Path $Launch)) "installed launcher removed"
Check (Test-Path (Join-Path $SandboxHome ".agents\skills\saipen\USER-NOTES.md")) "user file inside the skill dir survived uninstall"
if (Test-Path (Join-Path $SandboxHome ".claude\CLAUDE.md")) {
    $after = Get-Content (Join-Path $SandboxHome ".claude\CLAUDE.md") -Raw
    Check ($after -match "my own claude notes") "user's own CLAUDE.md content survived uninstall"
    Check ($after -notmatch "SAIPEN") "marked block removed from CLAUDE.md"
}

# ------------------------------------------------------------- 5. reinstall
Say ""; Say "=== reinstall ==="
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Clone "bootstrap\inject.ps1") *>> $Log
Gate $LASTEXITCODE "reinstall"
Check (Test-Path $Launch) "launcher present after reinstall"
Push-Location $Project
$out2 = & $Launch validate 2>&1 | Out-String
Gate $LASTEXITCODE "validate after reinstall"
Check ($out2 -match "Conformance:\s*CURRENT_PASS") "validate reported PASS after reinstall"
Pop-Location

Say ""
Say "================================================"
Say "steps: $script:step   failures: $script:fail"
Say "================================================"
exit $script:fail

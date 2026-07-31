param([string]$ProjectRoot)

$ErrorActionPreference = "Stop"
$projectRootWasSet = $PSBoundParameters.ContainsKey("ProjectRoot")

function Resolve-ProjectRoot([string]$explicitRoot, [bool]$explicitSet) {
    $start = (Get-Location).Path
    if ($explicitSet) {
        if ([string]::IsNullOrEmpty($explicitRoot)) {
            throw "explicit project root requires a non-empty path"
        }
        try { $root = (Resolve-Path -LiteralPath $explicitRoot -ErrorAction Stop).Path }
        catch { throw "explicit project root is not a directory: $explicitRoot" }
        if (-not (Test-Path -LiteralPath (Join-Path $root ".saipen") -PathType Container)) {
            throw "explicit project root has no .saipen: $root"
        }
        return $root
    }

    if (Get-Command git -ErrorAction SilentlyContinue) {
        $top = & git -C $start rev-parse --show-toplevel 2>$null
        $topStatus = $LASTEXITCODE
        if ($topStatus -eq 0) {
            $common = & git -C $start rev-parse --path-format=absolute --git-common-dir 2>$null
            if ($LASTEXITCODE -ne 0) { throw "cannot resolve Git common directory from $start" }
            $common = [string]($common | Select-Object -First 1)
            $top = [string]($top | Select-Object -First 1)
            $common = (Resolve-Path -LiteralPath $common -ErrorAction Stop).Path
            $commonParent = Split-Path -Parent $common
            $root = if ((Split-Path -Leaf $common).ToLowerInvariant() -eq ".git" -and
                (Test-Path -LiteralPath (Join-Path $commonParent ".saipen") -PathType Container)) {
                $commonParent
            } else { $top }
            $root = (Resolve-Path -LiteralPath $root -ErrorAction Stop).Path
            if (-not (Test-Path -LiteralPath (Join-Path $root ".saipen") -PathType Container)) {
                throw "Git project root owns no .saipen: $root; pass -ProjectRoot PATH to export another project"
            }
            return $root
        }
    }

    $cursor = [System.IO.DirectoryInfo]$start
    while ($null -ne $cursor) {
        if (Test-Path -LiteralPath (Join-Path $cursor.FullName ".saipen") -PathType Container) {
            return $cursor.FullName
        }
        $cursor = $cursor.Parent
    }
    throw "no owning .saipen found from $start"
}

try {
    $ownerRoot = Resolve-ProjectRoot $ProjectRoot $projectRootWasSet
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
$saipenDir = Join-Path -Path $ownerRoot -ChildPath ".saipen"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipName = "saipen_export_$timestamp.zip"
$zipPath = Join-Path -Path $ownerRoot -ChildPath $zipName

Write-Host "saipen state exporter"
Write-Host "------------------------------------------------------------"
Write-Host "Archiving: $saipenDir"
try {
    Compress-Archive -Path $saipenDir -DestinationPath $zipPath -Force -ErrorAction Stop
} catch {
    Write-Host "FAILED: $_" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $zipPath)) {
    Write-Host "FAILED: archive not found at $zipPath after Compress-Archive reported success" -ForegroundColor Red
    exit 1
}
Write-Host "Done. Export saved to: $zipPath"
Write-Host "------------------------------------------------------------"

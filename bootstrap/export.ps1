$ErrorActionPreference = "Continue"

$projectRoot = (Get-Location).Path
$saipenDir = Join-Path -Path $projectRoot -ChildPath ".saipen"

if (-not (Test-Path $saipenDir)) {
    Write-Host "No .saipen directory found in $projectRoot."
    exit 1
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipName = "saipen_export_$timestamp.zip"
$zipPath = Join-Path -Path $projectRoot -ChildPath $zipName

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

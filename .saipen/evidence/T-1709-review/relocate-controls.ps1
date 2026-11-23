$ErrorActionPreference = 'Stop'
$t1709Evidence = [IO.Path]::GetFullPath('V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\.saipen\evidence\T-1709-review')
$t1709Destination = [IO.Path]::GetFullPath('V:\_TEMP_\saipen-t1709-control-subjects-20261011T0515Z')
$t1709Manifest = Join-Path $t1709Evidence 'control-relocation.json'
if ((Test-Path -LiteralPath $t1709Destination) -or (Test-Path -LiteralPath $t1709Manifest)) {
    throw 'Existing relocation or destination must not be overwritten'
}
$t1709Sources = @(Get-ChildItem -LiteralPath $t1709Evidence -Directory -Filter 'subject-*')
$t1709Plan = @()
foreach ($t1709Source in $t1709Sources) {
    $t1709From = [IO.Path]::GetFullPath($t1709Source.FullName)
    $t1709To = [IO.Path]::GetFullPath((Join-Path $t1709Destination $t1709Source.Name))
    if (-not $t1709From.StartsWith($t1709Evidence + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source escapes the owned control directory'
    }
    if (-not $t1709To.StartsWith($t1709Destination + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Destination escapes the explicitly named task directory'
    }
    if (($t1709Source.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'Control root must be an ordinary owned directory'
    }
    $t1709Plan += [ordered]@{ stage = $t1709Source.Name; original = $t1709From; relocated = $t1709To }
}
New-Item -ItemType Directory -Path $t1709Destination | Out-Null
foreach ($t1709Item in $t1709Plan) {
    Move-Item -LiteralPath $t1709Item.original -Destination $t1709Item.relocated
}
[ordered]@{
    reason = 'Whole Git clones are local instrument subjects, outside the deliverable inventory. Original result records remain unchanged; these are their current locators.'
    controls = $t1709Plan
    portable_bundle = '.saipen/evidence/T-1709-review/control-subjects.zip'
    bundle_sha256 = (Get-FileHash -LiteralPath (Join-Path $t1709Evidence 'control-subjects.zip') -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $t1709Manifest -Encoding utf8
[ordered]@{ moved = $t1709Plan.Count; destination = $t1709Destination; manifest = $t1709Manifest } | ConvertTo-Json -Compress

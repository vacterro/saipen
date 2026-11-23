$ErrorActionPreference = 'Stop'
$t1803SchemaEvidence = Join-Path (Get-Location) '.saipen/evidence/T-1803-archived-improve'
& saipen validate --json 2>&1 | Tee-Object -FilePath (Join-Path $t1803SchemaEvidence 'conformance-schema-preflight.json')
$t1803SchemaPreflightExit = $LASTEXITCODE
if ($t1803SchemaPreflightExit -ne 0) {
    Write-Output "SCHEMA_VERIFY_STOP conformance_preflight=$t1803SchemaPreflightExit"
    return
}
$t1803SchemaPair = @(& saipen work regression T-1803 --file .saipen/evidence/T-1803-archived-improve/schema-regression-contract.json --json 2>&1)
$t1803SchemaPairExit = $LASTEXITCODE
[System.IO.File]::WriteAllText((Join-Path $t1803SchemaEvidence 'native-schema-regression-result.json'), ($t1803SchemaPair -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
$t1803SchemaPair
if ($t1803SchemaPairExit -ne 0) {
    Write-Output "SCHEMA_VERIFY_STOP regression=$t1803SchemaPairExit"
    return
}
& python -B tools/core_unit.py evidence T-1803 2>&1 | Tee-Object -FilePath (Join-Path $t1803SchemaEvidence 'core-unit-schema.txt')
$t1803SchemaFamilyExit = $LASTEXITCODE
if ($t1803SchemaFamilyExit -ne 0) {
    Write-Output "SCHEMA_VERIFY_STOP family=$t1803SchemaFamilyExit"
    return
}
& saipen validate --json 2>&1 | Tee-Object -FilePath (Join-Path $t1803SchemaEvidence 'conformance-schema.json')
$t1803SchemaConformanceExit = $LASTEXITCODE
Write-Output "SCHEMA_VERIFY_COMPLETE regression=$t1803SchemaPairExit family=$t1803SchemaFamilyExit conformance=$t1803SchemaConformanceExit"

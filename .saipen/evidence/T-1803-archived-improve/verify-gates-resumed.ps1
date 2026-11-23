$ErrorActionPreference = 'Stop'
$t1803Evidence = Join-Path (Get-Location) '.saipen/evidence/T-1803-archived-improve'
$t1803Pair = @(& saipen work regression T-1803 --file .saipen/evidence/T-1803-archived-improve/regression-contract.json --json 2>&1)
$t1803PairExit = $LASTEXITCODE
[System.IO.File]::WriteAllText((Join-Path $t1803Evidence 'native-regression-resumed.json'), ($t1803Pair -join [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
$t1803Pair
if ($t1803PairExit -ne 0) {
    Write-Output "VERIFY_GATES_STOP regression exit=$t1803PairExit"
    return
}
& python -B tools/core_unit.py evidence T-1803 2>&1 | Tee-Object -FilePath (Join-Path $t1803Evidence 'core-unit-resumed.txt')
$t1803FamilyExit = $LASTEXITCODE
if ($t1803FamilyExit -ne 0) {
    Write-Output "VERIFY_GATES_STOP family exit=$t1803FamilyExit"
    return
}
& saipen validate --json 2>&1 | Tee-Object -FilePath (Join-Path $t1803Evidence 'conformance-resumed.json')
$t1803ConformanceExit = $LASTEXITCODE
Write-Output "VERIFY_GATES_COMPLETE regression=$t1803PairExit family=$t1803FamilyExit conformance=$t1803ConformanceExit"

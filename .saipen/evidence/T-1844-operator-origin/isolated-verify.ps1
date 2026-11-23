$ErrorActionPreference = 'Stop'
$verifyTemp = 'V:\_SAIPEN_VERIFY_\T1844'
$env:TEMP = $verifyTemp
$env:TMP = $verifyTemp
$evidenceDir = Join-Path (Get-Location) '.saipen/evidence/T-1844-operator-origin'
$contracts = @('goal', 'diagnosis', 'preview', 'node', 'carrier')
foreach ($contractName in $contracts) {
    $contractPath = Join-Path $evidenceDir "final-$contractName-regression.json"
    $result = & saipen work regression T-1844 --file $contractPath --json
    $code = $LASTEXITCODE
    $result | Set-Content -LiteralPath (Join-Path $evidenceDir "isolated-$contractName-result.json") -Encoding utf8NoBOM
    $result
    if ($code -ne 0) { exit $code }
}
& 'C:\ProgramData\SAI\SAIPEN\python\3.11.9-64\python.exe' -B tools/core_unit.py evidence T-1844 --jobs 6 --fresh 2>&1 | Tee-Object -LiteralPath (Join-Path $evidenceDir 'isolated-full-family-console.log')
exit $LASTEXITCODE

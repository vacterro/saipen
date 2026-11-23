$ErrorActionPreference = 'Stop'
$gateProcessId = 15824
$gateProcess = Get-Process -Id $gateProcessId
$marker = Get-Content -LiteralPath '.saipen\cache\inflight\core-unit.json' -Raw | ConvertFrom-Json
if ($marker.pid -ne $gateProcessId) { throw 'Gate owner changed; inspect original tool session 71912' }
$created = [DateTimeOffset]::new($gateProcess.StartTime.ToUniversalTime()).ToUnixTimeSeconds()
if ([Math]::Abs($created - $marker.pid_created) -gt 1) { throw 'Gate process identity changed' }
$ownedRuns = Get-ChildItem -LiteralPath $env:TEMP -Directory -Filter 'saipen-core-unit-*' | Where-Object {
  $stamp = Join-Path $_.FullName 'owner.json'
  (Test-Path -LiteralPath $stamp) -and ((Get-Content -LiteralPath $stamp -Raw | ConvertFrom-Json).pid -eq $gateProcessId)
}
$shards = @()
foreach ($ownedRun in $ownedRuns) {
  foreach ($spoolFile in (Get-ChildItem -LiteralPath $ownedRun.FullName -Filter 'stderr' -File -Recurse -Depth 2)) {
    $readStream = [IO.FileStream]::new($spoolFile.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
    $streamReader = [IO.StreamReader]::new($readStream,[Text.Encoding]::UTF8)
    try { $streamText = $streamReader.ReadToEnd() } finally { $streamReader.Dispose() }
    $shards += [ordered]@{
      run=$ownedRun.Name
      observed_result_lines=[regex]::Matches($streamText,'(?m)\.\.\. (?:ok|skipped[^\r\n]*|FAIL|ERROR)\r?$').Count
      chars=$streamText.Length
      tail=($streamText -split "`n" | Select-Object -Last 2)
    }
  }
}
[ordered]@{
  pid=$gateProcessId
  tool_session_id=71912
  live=$true
  observed_at=[DateTime]::UtcNow.ToString('o')
  observed_result_lines=($shards | ForEach-Object { $_.observed_result_lines } | Measure-Object -Sum).Sum
  shards=$shards
  limit='Live progress only. The original session and final typed family record own completion and verdict.'
} | ConvertTo-Json -Depth 5

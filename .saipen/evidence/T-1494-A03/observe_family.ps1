param([Parameter(Mandatory=$true)][int]$FamilyPid,
      [Parameter(Mandatory=$true)][string]$SpoolPath)
$ErrorActionPreference = 'Stop'
$proofRoot = $PSScriptRoot
$resolvedSpool = (Resolve-Path -LiteralPath $SpoolPath).Path
if ($resolvedSpool.StartsWith((Resolve-Path -LiteralPath (Join-Path $proofRoot '..\..\..')).Path,
        [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Observer target is inside source tree' }
$watchTag = 'T1494A03-family-stderr-' + $FamilyPid
$familyWatcher = [System.IO.FileSystemWatcher]::new($resolvedSpool, 'stderr')
$familyWatcher.NotifyFilter = [System.IO.NotifyFilters]::LastWrite -bor [System.IO.NotifyFilters]::Size
$registration = Register-ObjectEvent -InputObject $familyWatcher -EventName Changed -SourceIdentifier $watchTag
$familyWatcher.EnableRaisingEvents = $true
function Save-OwnedSpool {
    foreach ($streamName in @('stdout','stderr')) {
        $streamPath = Join-Path $resolvedSpool $streamName
        if (Test-Path -LiteralPath $streamPath -PathType Leaf) {
            try {
                $readStream = [System.IO.FileStream]::new($streamPath, [System.IO.FileMode]::Open,
                    [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete)
                $readBuffer = [System.IO.MemoryStream]::new()
                try { $readStream.CopyTo($readBuffer); $streamBytes = $readBuffer.ToArray() }
                finally { $readStream.Dispose(); $readBuffer.Dispose() }
                [System.IO.File]::WriteAllBytes((Join-Path $proofRoot ('core-family-' + $streamName + '.txt')), $streamBytes)
            } catch [System.IO.FileNotFoundException] { }
        }
    }
}
try {
    Save-OwnedSpool
    while (Get-Process -Id $FamilyPid -ErrorAction SilentlyContinue) {
        $notification = Wait-Event -SourceIdentifier $watchTag -Timeout 30
        if ($null -ne $notification) {
            Save-OwnedSpool
            Get-Event -SourceIdentifier $watchTag -ErrorAction SilentlyContinue | Remove-Event
        }
    }
    Save-OwnedSpool
} finally {
    Unregister-Event -SourceIdentifier $watchTag -ErrorAction SilentlyContinue
    $familyWatcher.Dispose()
}
$captured = Get-Content -LiteralPath (Join-Path $proofRoot 'core-family-stderr.txt') -Raw
$summaryMatches = [regex]::Matches($captured, '(?m)^Ran (\d+) tests in ([0-9.]+)s\r?$')
$verdictMatches = [regex]::Matches($captured, '(?m)^(OK|FAILED)(?: \(([^\r\n]*)\))?\r?$')
$roster = @($captured -split '\r?\n' | Where-Object { $_ -match ' \.\.\. skipped ' })
$receipt = [ordered]@{ family_pid=$FamilyPid; source_spool=$resolvedSpool;
    observer='event-driven read-only copy; canonical runner unchanged';
    summaries=@($summaryMatches | ForEach-Object { $_.Value });
    verdicts=@($verdictMatches | ForEach-Object { $_.Value }); skipped_roster=$roster }
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $proofRoot 'core-family-observer.json') -Encoding utf8NoBOM
$receipt | ConvertTo-Json -Depth 5

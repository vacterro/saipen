# Operator-side client for an already-running SAI Accounts broker pipe.
# Sends one allowlisted JSON request; the broker answers under the managed
# account's own token. No credentials are read, sent or stored.
param([Parameter(Mandatory)][string]$Sid, [string]$Json, [string]$JsonFile,
      [string]$Scope = 'op-1f17624fa8051f44', [int]$TimeoutMs = 120000)
if ($JsonFile) { $Json = (Get-Content -Raw -LiteralPath $JsonFile).Trim() }
$sha = [Security.Cryptography.SHA256]::Create()
$fp = ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Sid.ToLower())) | ForEach-Object { $_.ToString('x2') }) -join ''
$pipe = "SAI.Accounts.$Scope.$($fp.Substring(0,16))"
$c = New-Object IO.Pipes.NamedPipeClientStream('.', $pipe, [IO.Pipes.PipeDirection]::InOut,
    [IO.Pipes.PipeOptions]::None, [Security.Principal.TokenImpersonationLevel]::Impersonation)
$c.Connect(5000)
$w = New-Object IO.StreamWriter($c); $w.WriteLine($Json); $w.Flush()
$r = New-Object IO.StreamReader($c)
$task = $r.ReadLineAsync()
if (-not $task.Wait($TimeoutMs)) { '{"client":"TIMEOUT"}'; exit 3 }
$task.Result
$c.Dispose()

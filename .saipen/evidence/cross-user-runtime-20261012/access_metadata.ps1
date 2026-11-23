$ErrorActionPreference = 'Stop'
$taskOutput = Join-Path $PSScriptRoot 'access-metadata.json'
if (Test-Path -LiteralPath $taskOutput) { throw 'Preserve immutable access metadata.' }
$taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskAccount = Get-LocalUser -Name 'SAIAG_9fabb0d5'
$taskSid = $taskAccount.SID.Value
$taskRoots = @('V:\___VAC\__K\__CODE\_PY\_SMART_VAC_CLEANER', 'V:\___VAC\__K\__CODE\_TAMPERMONKEY\_SUNO_DOWNLOADER')
$taskPaths = @('V:\', 'V:\___VAC', 'V:\___VAC\__K', 'V:\___VAC\__K\__CODE',
    'V:\___VAC\__K\__CODE\_PY', 'V:\___VAC\__K\__CODE\_TAMPERMONKEY',
    'C:\ProgramData\SAI\SAIPEN') + $taskRoots
$taskBefore = @{}
foreach ($taskRoot in $taskRoots) {
    foreach ($taskName in @('STATE.md', 'BOARD.md', 'LOG.md', 'IDENTITY.md', 'MANIFEST.json')) {
        $taskFile = Join-Path (Join-Path $taskRoot '.saipen') $taskName
        if (Test-Path -LiteralPath $taskFile) {
            $taskBefore[$taskFile] = (Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
}
$taskAcls = foreach ($taskPath in $taskPaths) {
    try {
        $taskItem = Get-Item -LiteralPath $taskPath -Force
        $taskAcl = Get-Acl -LiteralPath $taskPath
        [ordered]@{path=$taskPath;attributes=[string]$taskItem.Attributes;owner=$taskAcl.Owner;
            protected=$taskAcl.AreAccessRulesProtected;sddl=$taskAcl.Sddl;
            relevant_aces=@($taskAcl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) |
                Where-Object { $_.IdentityReference.Value -in @($taskSid, 'S-1-1-0', 'S-1-5-11', 'S-1-5-32-545') } |
                ForEach-Object { [ordered]@{sid=$_.IdentityReference.Value;type=[string]$_.AccessControlType;
                    rights=[string]$_.FileSystemRights;inherited=$_.IsInherited;
                    inheritance=[string]$_.InheritanceFlags;propagation=[string]$_.PropagationFlags} })}
    } catch {
        [ordered]@{path=$taskPath;error_type=$_.Exception.GetType().FullName;hresult=$_.Exception.HResult;
            detail=$_.Exception.Message;observed_by=$taskIdentity.Name}
    }
}
$taskGrants = Get-Content -LiteralPath 'C:\ProgramData\SAI\Accounts\grants.json' -Raw | ConvertFrom-Json
$taskGranted = @($taskGrants | Where-Object { $_.target_sid -eq $taskSid -and $_.workdir -in $taskRoots } |
    Select-Object target_sid,workdir,created,last_seen)
$taskProcesses = @(Get-CimInstance Win32_Process -Filter "Name LIKE 'Antigravity%'")
$taskProcessRows = foreach ($taskProcess in $taskProcesses) {
    $taskOwner = Invoke-CimMethod -InputObject $taskProcess -MethodName GetOwner
    $taskOwnerSid = Invoke-CimMethod -InputObject $taskProcess -MethodName GetOwnerSid
    [ordered]@{pid=$taskProcess.ProcessId;created=$taskProcess.CreationDate;executable=$taskProcess.ExecutablePath;
        account=$taskOwner.User;domain=$taskOwner.Domain;owner_result=$taskOwner.ReturnValue;
        sid=$taskOwnerSid.Sid;sid_result=$taskOwnerSid.ReturnValue}
}
$taskChanged = @($taskBefore.Keys | Where-Object {
    (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskBefore[$_]
})
if ($taskChanged.Count) { throw 'Protected consumer records changed during read-only metadata observation.' }
$taskValue = [ordered]@{captured_utc=[DateTime]::UtcNow.ToString('o');
    observer=@{account=$taskIdentity.Name;sid=$taskIdentity.User.Value};
    reported_ag3_account=@{name=$taskAccount.Name;sid=$taskSid;enabled=$taskAccount.Enabled;last_logon=$taskAccount.LastLogon};
    project_grants=$taskGranted;paths=$taskAcls;antigravity_name_filter_processes=@($taskProcessRows);
    canonical_hashes=$taskBefore;canonical_unchanged=$true;acl_mutations=0;impersonation=$false;
    real_ag3_execution=$false;limit='Operator-token metadata only. An enabled account or grant is not effective access proof; an empty executable-name filter is not proof all host channels are unavailable.'}
[IO.File]::WriteAllText($taskOutput, ($taskValue | ConvertTo-Json -Depth 10) + "`n", [Text.UTF8Encoding]::new($false))
[ordered]@{evidence=$taskOutput;account=$taskAccount.Name;sid=$taskSid;grants=$taskGranted.Count;
    protected_records=$taskBefore.Count;canonical_unchanged=$true;acl_mutations=0;real_ag3_execution=$false} | ConvertTo-Json -Compress

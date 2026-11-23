$ErrorActionPreference = 'Stop'
$taskRoot = 'V:\___VAC\__K\__CODE\_TAMPERMONKEY\_SUNO_DOWNLOADER'
$taskUser = 'saiag_9fabb0d5'
$taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$taskAccount = Get-LocalUser -Name $taskUser
$taskSid = $taskAccount.SID.Value
$taskPaths = @('V:\', 'V:\___VAC', 'V:\___VAC\__K', 'V:\___VAC\__K\__CODE',
    'V:\___VAC\__K\__CODE\_TAMPERMONKEY', $taskRoot, "$taskRoot\.saipen", "$taskRoot\.saipen\MANIFEST.json")
$taskBefore = @{}
foreach ($taskName in @('STATE.md', 'BOARD.md', 'LOG.md', 'IDENTITY.md')) {
    $taskBefore[$taskName] = (Get-FileHash -LiteralPath "$taskRoot\.saipen\$taskName" -Algorithm SHA256).Hash.ToLowerInvariant()
}
$taskAclRows = foreach ($taskPath in $taskPaths) {
    try {
        $taskItem = Get-Item -LiteralPath $taskPath -Force
        $taskAcl = Get-Acl -LiteralPath $taskPath
        [ordered]@{path=$taskPath;exists=$true;attributes=[string]$taskItem.Attributes;owner=$taskAcl.Owner;
            protected=$taskAcl.AreAccessRulesProtected;sddl=$taskAcl.Sddl;
            relevant_aces=@($taskAcl.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier]) |
                Where-Object { $_.IdentityReference.Value -in @($taskSid,'S-1-1-0','S-1-5-11','S-1-5-32-545') } |
                ForEach-Object { [ordered]@{sid=$_.IdentityReference.Value;type=[string]$_.AccessControlType;
                    rights=[string]$_.FileSystemRights;inherited=$_.IsInherited;
                    inheritance=[string]$_.InheritanceFlags;propagation=[string]$_.PropagationFlags} })}
    } catch {
        [ordered]@{path=$taskPath;observed_by=$taskIdentity.Name;error_type=$_.Exception.GetType().FullName;
            error=$_.Exception.Message;hresult=$_.Exception.HResult;classification='read diagnostic failed'}
    }
}
$taskGrants = Get-Content -LiteralPath 'C:\ProgramData\SAI\Accounts\grants.json' -Raw | ConvertFrom-Json
$taskMatchingGrants = @($taskGrants | Where-Object { $_.target_sid -eq $taskSid -and $_.workdir -eq $taskRoot } |
    Select-Object target_sid,workdir,created,last_seen)
$taskGroups = @(Get-LocalGroup | ForEach-Object {
    $taskGroup = $_
    Get-LocalGroupMember -Group $taskGroup -ErrorAction SilentlyContinue |
        Where-Object { $_.SID.Value -eq $taskSid } |
        ForEach-Object { [ordered]@{group=$taskGroup.Name;name=$_.Name;sid=$_.SID.Value} }
})
$taskState = Get-Content -LiteralPath "$taskRoot\.saipen\STATE.md" -Raw
$taskRuntimeMatch = [regex]::Match($taskState, 'saipen_home:\s*"([^"\r\n]+)"')
$taskRuntime = $taskRuntimeMatch.Groups[1].Value
$taskRuntimeRows = foreach ($taskName in @('tools/saipen_engine/audit_manifest.py','tools/saipen_engine/paths.py','tools/saipen_engine/reconcile.py','VERSION')) {
    foreach ($taskHome in @((Get-Location).Path, $taskRuntime)) {
        $taskFile = Join-Path $taskHome $taskName
        try { [ordered]@{path=$taskFile;sha256=(Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()} }
        catch { [ordered]@{path=$taskFile;error=$_.Exception.Message} }
    }
}
$taskAfter = @{}
foreach ($taskName in @('STATE.md', 'BOARD.md', 'LOG.md', 'IDENTITY.md')) {
    $taskAfter[$taskName] = (Get-FileHash -LiteralPath "$taskRoot\.saipen\$taskName" -Algorithm SHA256).Hash.ToLowerInvariant()
}
$taskUnchanged = @($taskBefore.Keys | Where-Object { $taskBefore[$_] -ne $taskAfter[$_] }).Count -eq 0
$taskReport = [ordered]@{
    captured_utc=[DateTime]::UtcNow.ToString('o');diagnostic_identity=@{account=$taskIdentity.Name;sid=$taskIdentity.User.Value;
        authentication=$taskIdentity.AuthenticationType;is_system=$taskIdentity.IsSystem};
    reported_execution_account=@{account=$taskAccount.Name;sid=$taskSid;enabled=$taskAccount.Enabled;
        description=$taskAccount.Description;direct_local_groups=$taskGroups;
        token_executed=$false;limit='Account and ACL metadata are confirmed; the affected process token and its restricted groups/privileges were not obtained.'};
    authorized_project_grants=$taskMatchingGrants;paths=$taskAclRows;project_state=$taskState;
    runtime_files=$taskRuntimeRows;canonical_before=$taskBefore;canonical_after=$taskAfter;
    canonical_bytes_unchanged=$taskUnchanged;acl_mutations=0;affected_project_writes=0;
    limit='Read-only, explicitly bound project and ancestor metadata. No Test-Path inference, account impersonation, grant, ownership change, runtime deployment, or project recovery.'
}
$taskOut = Join-Path $PSScriptRoot 'read-only-diagnostics.json'
if (Test-Path -LiteralPath $taskOut) { throw 'Diagnostic evidence already exists; choose a fresh name rather than overwrite history.' }
[IO.File]::WriteAllText($taskOut, ($taskReport | ConvertTo-Json -Depth 10) + "`n", [Text.UTF8Encoding]::new($false))
[ordered]@{evidence=$taskOut;account=$taskAccount.Name;sid=$taskSid;project=$taskRoot;
    project_bytes_unchanged=$taskUnchanged;acl_mutations=0} | ConvertTo-Json -Compress

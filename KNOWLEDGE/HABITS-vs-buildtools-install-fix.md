# HABITS: VS Build Tools install failure — MSI "cannot find the file specified"

## Symptom

Visual Studio Installer / Build Tools 2022 fails on every MSI package:

```
Package 'Microsoft.Build.FileTracker.Msi,version=...' failed to install.
Return code: 2
Return code details: The system cannot find the file specified.
```

Setup log (`V:\_TEMP_\dd_setup_*_002_*.log`) ends with:

```
Error: Failed to access database: C:\ProgramData\Microsoft\VisualStudio\Packages\...
MainEngineThread is returning 2
```

Also: `C:\ProgramData\Microsoft\VisualStudio\Packages` is empty (0 MB) — downloads
"finish" instantly but nothing persists.

## Root cause

Broken ACLs on the installer cache path. msiexec installs run as **SYSTEM**,
but the cache folders had inheritance disabled and only the user account
(`vac34`) in the ACL — **no SYSTEM / Administrators**:

```
C:\ProgramData\Microsoft\VisualStudio         → only vac34 (no SYSTEM)
C:\ProgramData\Microsoft\VisualStudio\Packages → only vac34 (no SYSTEM)
C:\ProgramData\Microsoft                      → Administrators + vac34 (no SYSTEM)
```

Result: the downloader could not write package payloads into the cache, and
SYSTEM could not read them during MSI install → MSI reports file-not-found.

Trigger (any of): manual ACL edits, third-party cleaners/AV, interrupted install
that recreated folders with a user-only DACL.

## Fix (run as Administrator)

```powershell
icacls "C:\ProgramData\Microsoft" /reset /C /Q
icacls "C:\ProgramData\Microsoft\VisualStudio" /reset /T /C /Q
```

Verify SYSTEM + Administrators + Users are back:

```powershell
icacls "C:\ProgramData\Microsoft\VisualStudio\Packages"
# NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F)  ← must be present
```

Then retry the install.

## Verified quiet install commands

The old installed `setup.exe` (4.9.50.x) rejects `--log` (exit 87) and REQUIRES
`--productId` + a channel. Do NOT use the `vs_BuildTools.exe` bootstrapper for
silent installs on this machine — it injects `--log` which the old installer
does not understand.

Working form (PowerShell, elevated, fire-and-forget):

```powershell
Start-Process -FilePath "C:\Program Files (x86)\Microsoft Visual Studio\Installer\setup.exe" `
  -ArgumentList @('install','--productId','Microsoft.VisualStudio.Product.BuildTools',`
    '--channelId','VisualStudio.17.Release',`
    '--installPath','S:\VSBuildTools',`
    '--add','Microsoft.VisualStudio.Workload.VCTools',`
    '--includeRecommended','--quiet','--norestart','--nocache')
```

- `--nocache` keeps C: clean (package cache is always C:\ProgramData\...).
- Off-drive `--installPath` (S:) because C: is nearly full.
- Logs: `%TEMP%\dd_installer_*.log`; success = `Exit Code: 0` + `Completed install`.
- Do NOT run `setup.exe` with `-RedirectStandardOutput` — it breaks the WPF
  installer (early exit 1, no log).

## Do not repeat

- Do not delete/recreate `C:\ProgramData\Microsoft\VisualStudio` manually.
- If a VS install fails, check the ACL chain FIRST, not the package list.
- Keep ≥20 GB free on the package-cache drive (C:) for repairs.

## Can this revert on reboot? — audited (2026-08-16)

ACLs are NTFS metadata; nothing reverts them on their own. Vectors that COULD
reset them were all checked and are ABSENT:

- Domain GPO: machine is WORKGROUP, not domain-joined → no AD policy.
- Local GPO file-system security: `C:\Windows\System32\GroupPolicy\Machine\...
  \SecEdit\GptTmpl.inf` does not exist → no File System security policy.
- VS setup *policies*: `HKLM\SOFTWARE\Policies\Microsoft\VisualStudio\Setup`
  (and WOW6432Node) absent. Only VS Installer's own settings present
  (`SharedInstallationPath`, `KeepDownloadedPayloads=0`) — not policies.
- Windows Installer policies: only `MaxPatchCacheSize=0` (default).
- Scheduled tasks: none reference `icacls/setacl/VS/ProgramData`.
- GPO startup scripts: none. `Winlogon` Userinit/Shell = defaults.
- Run keys: only Autodesk/Adobe/PS Tray Factory (benign).
- Third-party AV: none registered (SecurityCenter2 empty, no AV processes).

Remaining realistic risk (NOT reboot): a disk-cleaner/AV/one-off script that
deletes or re-ACLs `C:\ProgramData\Microsoft\VisualStudio`. If the old symptom
returns, re-run the two `icacls /reset` commands from the fix section.

## Machine state after fix (2026-08-16)

- VS Build Tools 2022 **17.14.38** at `S:\VSBuildTools` (MSVC v143 14.44.35207,
  Windows SDK 10.0.26100) — `vswhere` shows `isComplete: true`.
- Rust **1.97.1 MSVC** — default toolchain `stable-x86_64-pc-windows-msvc`
  (GNU toolchain kept, not default).
- Rust + MSVC link verified: `vcvars64.bat` + `rustc hello.rs` → hello.exe.
- Node v24.15.0, pnpm 11.22.0, WebView2 143 present.
- Smoke proof for Tauri: build env = `S:\VSBuildTools\VC\Auxiliary\Build\vcvars64.bat`.

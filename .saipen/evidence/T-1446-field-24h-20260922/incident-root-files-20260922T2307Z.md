# Incident: stray files at the saipen_home root during the 24H soak

Observed 2026-09-22 by astra (T-1471 session) while shipping T-1473.

## What appeared

Two empty files at the root of this repository (the soak project's
`saipen_home`), caught by `tools/validate.py` check `root-file-set`:

| file | created (UTC) |
|------|---------------|
| `BLOCKED` | 2026-09-22T23:07:24.686Z |
| ``M` `` | 2026-09-22T23:07:25.161Z |

Both were deleted after this record was taken; neither was committed.

## What ran at that instant

The only host tool call executing between 23:07:24.177Z and 23:07:25.287Z
(opencode.db `part` rows, every session) was the soak worker's
`saipen next --json`: session `ses_f34a278e3ffeXTpccNJs56CE1X`, provider
sairoute, model SAIFREN, cwd `V:\_TEMP_\t1363-zc8hv_xc`, host shell
PowerShell (resolves `saipen` to the installed `bin\saipen.cmd`).

Six seconds earlier (23:07:18Z) the same worker tried three manual canonical
edits (`echo ... >> ".saipen\LOG.md"` twice and
`(Get-Content .saipen\STATE.md) -replace 'phase: REVIEW','phase: DONE' |
Set-Content .saipen\STATE.md`). The saipen guard refused all three with
`PROTECTED_CANONICAL_NAMESPACE` -- "the host tool did not execute" -- and
the worker then closed T-22 through canonical operations.

## Why the names matter

The names are what cmd.exe makes of protocol text when a `>` inside it is
not quoted: MAINTENANCE.md carries `` `DEC: goal_waves N->M` `` (redirect
target ``M` ``) and phases/ship.md carries `-> BLOCKED` (target `BLOCKED`).
Two separate redirections, 0.5 s apart, into a process whose cwd was this
repository.

## What was ruled out

- `saipen next --json` itself: replayed under a Python audit hook with the
  worker's environment (`SAIPEN_AUTONOMY_RUN_ID`, `SAIPEN_AUTONOMY_WORKER`,
  `SAIPEN_LEASE_GENERATION`, `PWD`) against a disposable project; the only
  spawned process was `git rev-parse --show-toplevel`.
- `tools/validate.py --gate core`, `test_t1473_handback`,
  `test_dependency_resume_liveness`, and the T-1473 checkpoint commands:
  rerun, no stray file.
- the scheduled injector (ran 23:01:00Z, skipped DIRTY_SOURCE), the soak
  driver (no shell), the opencode plugins `saipen-guard.js` and
  `cbm-augment.ts` (spawn without a shell).

## Open

The writer is outside the engine's `next` path as replayed. Remaining
candidates: a runtime resync (`runtime_bootstrap._invoke_installer` ->
`bootstrap/inject.ps1`) triggered only in the worker's environment, and
the PowerShell -> `saipen.cmd` argument path. A field worker must not be able
to create files in `saipen_home` whatever it types.

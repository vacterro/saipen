# T-1634 -- the doctor judged an installation by evidence that was not its own

Two defects escaped T-1624 and were measured on the operator's machine within
minutes of its closure (2026-10-06, LOG E-12522 onward). Both made
`saipen host doctor` contradict something the installation itself could prove.
A third was found while explaining the second.

## What was observed

1. 13:21Z: `saipen host doctor` -> `claude HEALTHY_VERIFIED ... MECHANICAL`.
   13:23Z: `python -m unittest test_t1624_host_integration` (REVIEW rerun).
   13:24Z: `saipen host doctor` -> `claude AUTHORITY_UNAVAILABLE ...
   DEGRADED_UNVERIFIED`, reason `AUTHORITY_CLIENT_UNPROVEN`. The operator's
   `~/.saipen/health/claude.json` then read
   `"hook": "V:\\_TEMP_\\tmpf_n866s0\\home\\.claude\\hooks\\saipen-guard.py"`:
   a fixture's hook had written the operator's record, after asking the
   operator's live authority service.
2. 13:22Z: all-hosts `saipen host repair` -> seven `install:<host>: ok
   INSTALLED`, then `repair incomplete: codex STALE_RUNTIME, gemini
   STALE_RUNTIME`, rc 1. `python tools/install_host_guard.py codex --check`
   on the same profile answered `"current": true, "problems": []`.

## Mechanisms (measured, `*.txt` beside this file)

- **Foreign health record.** `host_integration._health_is_current` checked a
  record's age and nothing about who wrote it.
  `InstallerTests.as_the_host_runs_it` ran the bare installed command spelling
  (no `--home`, which is the point of that test) with the operator's profile.
  `leak_probe.py.txt` over 18 host-facing modules: exactly one writer
  (`leak-probe.txt`).
- **The interpreter of a cmd.exe spelling.** `install_host_guard`
  compares a configured hook command with the expected one "modulo the
  interpreter", unless `interpreter_missing(configured)`. That helper read only
  the FIRST split `_argv_of` returns, the POSIX one, which strips the
  backslashes of an unquoted path: `C:Usersvac34...python.exe` exists nowhere.
  Codex's `commandWindows` and the single command of Gemini and Kiro on Windows
  are that spelling. The launcher starts `...\python.EXE`; the installer's own
  process reports `...\python.exe`. So the doctor, run through the launcher,
  never matched an entry the installer had just written. `diag_codex2.py.txt`
  prints the two heads and `interpreter missing: True` for the Windows entry.
  Reproduced on a sandbox profile with the REAL installer
  (`repair_sandbox.py.txt`): `host repair` rc 1 `REPAIR_INCOMPLETE`, twice.
- **The inspected copy judged itself.** `_hook_facts` put
  `<runtime under inspection>/tools` first on `sys.path` and imported
  `install_host_guard` from there. The code deciding "current" belonged to the
  installation being judged, and a repair's own re-check ran the module it had
  just replaced.

My first explanation of the second defect was wrong (the check ROOT). Its test
passed against the unfixed code, which is how the error was caught; that test
is not in the tree.

## Repair

| file | change |
|------|--------|
| `tools/saipen_engine/host_integration.py` | `_health_is_current`: only a record whose `hook` is the installed hook file is evidence (`_same_file`); `_hook_facts`: imports the installer of the runtime that is running |
| `tools/install_host_guard.py` | `_interpreters_of`: the interpreter under each shell reading; `interpreter_missing` means missing under every reading; `interpreter_of` prefers the reading that exists |
| `tools/test_t1624_host_integration.py` | the bare-spelling child runs with the fixture profile and proves where its hook wrote; three product tests |

## Evidence

    REGRESSION-EVIDENCE FAIL verifier:cde2bf5a384b9060 subject:0f879f146cb2eb63   E-12542
    REGRESSION-EVIDENCE PASS verifier:cde2bf5a384b9060 subject:460cf696a6ee56e0   E-12543

- Fixture red control (profile line removed, restored byte-identical):
  `AssertionError: unexpectedly None : the fixture hook wrote its record
  outside the fixture`, then OK.
- Sandbox profile, real installer, through the launcher, after the repair:
  codex and gemini `hook current`, `host repair` rc 0 `HOST_REPAIRED`, twice.
- Leak probe on the repaired module: 70 tests OK, operator profile untouched.

## On the operator's machine, after the repair (2026-10-06 13:55-13:57Z)

- Family: `CORE-UNIT-EVIDENCE PASS`, 5268 ran, new_red 0, fingerprint
  `2e1e6400a9fd0382` (LOG E-12547).
- `saipen host repair` (all hosts): eight `install:<host>: ok INSTALLED`,
  `authority:stop: ok`, `authority:start: ok AUTHORITY_STARTED`, `repair
  complete: every installed host is on the canonical generation`, rc 0. The
  same command an hour earlier ended `repair incomplete: codex STALE_RUNTIME,
  gemini STALE_RUNTIME`, rc 1.
- `saipen host doctor` in a fresh process: every installed host `runtime
  current`; codex and gemini `hook current`; claude `HEALTHY_VERIFIED ...
  MECHANICAL`; `nothing to do`; rc 0.
- One real `claude -p` prompt in a disposable SAIPEN project: health
  `ADMITTED`, 279 ms, record written by `~/.claude/hooks/saipen-guard.py`.
- The formerly leaking module run again (`leak_probe.py`, 70 tests OK): the
  operator's health record untouched, and the doctor's claude row still
  `HEALTHY_VERIFIED` afterwards.

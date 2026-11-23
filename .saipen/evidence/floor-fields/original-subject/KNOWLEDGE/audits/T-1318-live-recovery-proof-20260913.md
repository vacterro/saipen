# T-1318 AC-05 — live canonical recovery proof, and the reachability defect it found

Date: 2026-09-13
Ticket: T-1318 (blocker for T-1317 steps 9-10)
Harness: `tools/test_opencode_live_session.py` (opt-in: `SAIPEN_LIVE_OPENCODE=1`)
Evidence: `.saipen/evidence/T-1317-opencode-live-session/` (`live-session-proof.json`,
`MANIFEST-live-session-T-1317.json`, `live-run-20260913d.log`)

## 1. Entry gate (the wave asked for this BEFORE any new work)

| item | state |
|---|---|
| T-1318 recovery command/operation exists | yes — bare `saipen recover` routes to `reconcile_protocol_state` |
| original malformed STATE preserved | yes — `.saipen/recovery/state-phase/<op_id>.STATE.md`, byte-identical |
| journaled recovery | yes — via `build_plan`/`apply_plan` |
| idempotent | yes — second call returns `CLEAN`, one artifact |
| legal-state refusal | yes — `CLEAN`, zero writes |
| corrupt/ambiguous refusal | yes — `VALIDATION_FAILED`, zero writes |
| **T-1317 fresh OpenCode recovery proof** | **NO — this run's job** |
| protected writes blocked | yes (unchanged) |
| ordinary work blocked while invalid | yes (unchanged) |
| recovery available while invalid | yes (unchanged) |

Item 7 was missing, so this run returned to the T-1318/T-1317 wave and did not
start the fleet-recovery preflight wave.

## 2. The defect the live proof found

The first live attempt of the recovery sequence produced:

```
bash  error      'pwd'                        SAIPEN_GUARD_REFUSAL: PROTOCOL_STATE_INVALID
bash  error      'echo POST_RECOVERY_ORDINARY_OK'  SAIPEN_GUARD_REFUSAL: PROTOCOL_STATE_INVALID
bash  error      'rm -f .saipen/STATE.md'     SAIPEN_GUARD_REFUSAL: PROTECTED_CANONICAL_NAMESPACE
bash  completed  'saipen recover'             (no output)          <-- nothing ran
```

`saipen recover` was ADMITTED by the guard (effect class `saipen_op`) and still
did nothing. Measured host facts, in order:

1. OpenCode's shell tool on this Windows host is **PowerShell**, not bash
   (proved by `ls -la <dir>` returning `Get-ChildItem: ... parameter 'la'`, and
   by `uname` resolving to Git's `uname.exe` from PATH).
2. PowerShell resolves a command only through `PATHEXT` (`.exe`/`.cmd`/`.bat`).
   An extensionless POSIX script named `saipen` is invisible there.
3. No `saipen` launcher exists on this machine at all: `where saipen` →
   *INFO: Could not find files for the given pattern(s).*
4. `guard_events._saipen_cli_verb` recognises the canonical surface ONLY as the
   literal leading token `saipen` (correct: path-routed, env-prefixed and
   wrapper forms are deliberately never canonical).

So the admitted canonical operation could never execute, while every other
consequential shell command was correctly refused. `KNOWN ROOT + INVALID STATE`
therefore still had no reachable legal action — the exact LIMISAW deadlock,
one layer below the layer T-1318 fixed.

## 3. The fix (adapter-side; the guard is NOT weakened)

`extensions/adapters/opencode/saipen-guard.js`, BUILD_ID
`T-1317-opencode-active-generation-20260913.4`:

- `ensureCliLaunchers(skill, pythonBin)` materialises, at plugin factory time,
  `<skill>/bin/saipen.cmd` (PowerShell/cmd) and `<skill>/bin/saipen` (POSIX),
  each exactly `python <installed saipen.py>`;
- the skill's `bin` directory is prepended to `process.env.PATH` (`Path` too on
  win32) so the host's child shells can resolve it;
- `cli_bin` is added to the bounded startup diagnostic so the evidence proves it;
- never throws: a launcher failure cannot change a guard verdict.

This is a translation fix, not an authority change: the launcher runs exactly
the documented CLI (`python .../tools/saipen.py`), and the guard still decides
every verdict. Nothing was added to the canonical verb vocabulary and no
wildcard/prefix matching was introduced.

## 4. Live proof (green, 8/8, `live-run-20260913d.log`)

Generation (isolated install built by `bootstrap/inject.sh`):

```
build_id              T-1317-opencode-active-generation-20260913.4
source_sha256         83beabbf07b877d0b24446e82d7cb33fcf792376fe135ec12499f298fd813abd
installed_sha256      83beabbf07b877d0b24446e82d7cb33fcf792376fe135ec12499f298fd813abd
loaded_module_sha256  ['83beabbf...813abd']
sha_triplet_equal     True
```

Three genuinely new processes, each `fresh_after_install: True`:

| session | pid | opencode session |
|---|---|---|
| good | 14012 | `ses_f661cece7ffe4Ze94wBQDMz0c4` |
| malformed | 19596 | `ses_f661cce01ffelUpNaVnjUDLk7Q` |
| recovered | 22636 | `ses_f661c1028ffeeWhRLBlkNzHrxv` |

`cli_bin` present in every factory diagnostic, e.g.
`...\home\.config\opencode\skills\saipen\bin`.

The malformed session, in host order — the full required semantics:

```
todowrite completed                        (native Todo works)
bash      'pwd'                            -> refused PROTOCOL_STATE_INVALID
bash      'saipen recover'                 -> completed, "code: REPAIRED"
bash      'echo POST_RECOVERY_ORDINARY_OK' -> completed, printed
bash      'rm -f .saipen/STATE.md'         -> refused PROTECTED_CANONICAL_NAMESPACE
```

and the post-recovery session (new process): `pwd` and `echo` both completed,
`IMPL` gone from STATE, exactly one preserved recovery artifact.

No `question` tool call and no root-question phrasing in any session;
the model answered `ROOT_KNOWN_RECOVERY_REQUIRED`, never `ROOT_UNKNOWN`.

## 5. Test deltas

- `tools/test_opencode_live_session.py`: `_git_project` now builds a genuinely
  RECOVERABLE malformed fixture (a real `transition to SCOUT`/`to BUILD` chain in
  LOG, `phase: IMPL` + `transition_from: DONE` in STATE, `T-001` live in BOARD);
  the harness-side `saipen` shim was REMOVED so the proof exercises the
  adapter's own launcher; added `test_7` (recovery repairs + forensic copy) and
  `test_8` (a new process admits ordinary work afterwards); path comparison is
  separator-normalised; ruff clean.
- Focused suites, after the change: adapter+reconcile+adaptive-runtime+admission
  **89 passed**; host-smoke+guard-hostile+actor-binding+guard-events
  **81 passed, 1 failed**.

## 6. The one open red, and what it means

`test_opencode_host_smoke.py::OpenCodeRealInstalledGeneration::…` is the
permanent "the REAL `~/.config/opencode` install equals the shipped artifact"
gate. It is red because the real home still carries the previous generation
(`5b435deb…`, `…20260913.3`) while the shipped source is now `83beabbf…`
(`…20260913.4`). That is the intended staleness signal, not a code defect: the
operator must run `bootstrap/inject.sh` (or `inject.ps1`) to publish the
accepted generation. No out-of-project write was performed from this run.

## 7. Not done in this run

- `bootstrap/inject.sh` was not run against the real home (§6).
- T-1318 and T-1317 were not closed canonically (no BOARD/STATE/LOG mutation was
  made by hand, by design).
- The fleet-recovery preflight wave (project-health preflight, safe auto-recovery
  orchestration, continuation envelope, `doctor` scanner) was NOT started; its
  ENTRY GATE requires item 7, which only this run proved.

# T-279 evidence — canonical control-plane launch and instance attribution for Windows-context Antigravity accounts

Ticket: `T-279 [P1]` — Antigravity accounts carry `execution_backend = windows_user` /
`managed_windows_user`, so AUDAPACK cannot select their Windows user session itself; delegate
execution to the SAI Accounts control plane (`sai-accounts launch <account_id> --workdir <project_root>`)
with a first-class execution mode (`STAGE_PLANE_LAUNCH`), attribute the returned real process `pid`
to `sai:<account_id>`, and fail closed without fallback whenever the plane is absent or rejects the launch.

## 1. Installed control-plane launch contract

`C:\ProgramData\SAI\Accounts\bin\sai-accounts.exe` exposes:

```
sai-accounts launch <canonical_account_id> --workdir <project_root>
```

and returns a structured `sai.accounts/launch/1` JSON envelope on stdout:

* Success (`windows_user` direct or `managed_windows_user` broker):
  `{"schema":"sai.accounts/launch/1","status":"launched","account_id":"<id>","provider_id":"antigravity","execution":"direct|broker","pid":<real_agy_pid>,"workdir":"<dir>"}`
* Top-level CLI validation failure:
  `{"schema":"sai.accounts/launch/1","error":{"code":"...","message":"..."}}`
* Broker execution failure (e.g. unmapped/ACL-denied workdir for a brokered Windows user):
  `{"schema":"sai.accounts/launch/1","account_id":"<id>","workdir":"<dir>","broker_context":"...","status":"WORKDIR_UNAVAILABLE","reason":"ACCESS_DENIED","execution":"broker"}`

Three of those fields carry less weight than the shape suggests, and the enforcement was
brought in line with what the installed generation-36 plane actually guarantees:

* **`schema`, `account_id` and `pid` are MANDATORY.** A launched envelope without the exact
  `sai.accounts/launch/1` schema, an exact canonical `account_id` and a positive non-bool
  integer `pid` is not a success and is never registered. Exact `account_id` matching is
  never weakened, so a foreign account's success can never be attributed to this one.
* **`provider_id` and `workdir` are OPTIONAL.** The plane need not state either and the
  launcher requires neither. When one is present and non-empty it is a claim about *this*
  launch, so it must be consistent with the request or the envelope fails closed (section 5).
* **`execution` is INFORMATIONAL.** `direct` and `broker` (plus the live-observed
  `current_user`) are broker routes for the same contract, not a mandatory enum: the value is
  carried on `LaunchResult` and is never a gate.

## 2. Implementation summary

* `audapack/sai_accounts.py`:
  * Added `LaunchResult`, `LAUNCH_TIMEOUT_S = 15.0`, `cached_account()`, `_redact_sids()`, and `launch(account_id, workdir, timeout=None)`.
  * Invokes `["launch", target_account, "--workdir", target_workdir]` as an `argv` list (no shell interpolation).
  * Verifies `status == "launched"`, `returned_account == target_account`, positive integer `pid` of the spawned Antigravity process, and — added by T-285 — the optional `provider_id` / `workdir` consistency checks; parses both `error.{code,message}` and broker `status`/`reason` envelopes; strips any `S-1-...` SID or `broker_context`.
* `audapack/cli_launchers.py`:
  * Added first-class `STAGE_PLANE_LAUNCH = "plane_launch"` (`is_plane_launch` property and `account_id` field on `CliResolution`, with `console_command=""` so no fake PowerShell command is smuggled into `resolved_command`).
  * Restricted plane launch to `_PLANE_LAUNCH_PROVIDERS = frozenset({"antigravity"})` and `_PLANE_SESSION_BACKENDS = frozenset({"windows_user", "managed_windows_user"})`.
* `audapack/launch_federation.py`:
  * Passed `account_id=entry.account_id` into `_apply_execution` and ensured `resolved_stage` transitions mark `unchanged=False` during reconciliation.
* `audapack/launch_authority.py` & `audapack/ui_qt/main_window.py`:
  * Extended `register_agent_process()` to accept an integer `pid` (from control-plane launch) as well as a `Popen`-like object.
  * Routed `resolution.is_plane_launch` in `MainWindow._launch_cli_launcher()` to `MainWindow._launch_plane_account()`, which calls `sai_accounts.launch(account_id, str(launch_target.cwd))` and registers `verdict.pid` under `cfg.id` (`sai:<account_id>`).
* `audapack/instances.py`:
  * Added `"agy.exe": "antigravity"` to `direct_processes` in `_is_probable_agent_window` and ignored executable/script paths (`.exe`, `.cmd`, `.bat`, `.ps1`, `.cjs`, `.js`) in `_window_names_another_root` so a spawned `C:\ProgramData\SAI\Accounts\bin\agy.exe` window is not misclassified as a foreign project root.

## 3. Hermetic & full test suite gates

The gates below are the T-279 **closure-hardening boundary** — the fail-closed schema /
account_id / pid closure landed, and the full suite was re-run on the frozen tree. They
supersede the earlier 120-passed / 2661-passed figures this file used to carry, which
described the pre-hardening implementation.

```
python -m pytest -q tests/test_plane_launch.py tests/test_launch_federation.py tests/test_sai_accounts_federation.py
143 passed

python -m ruff check audapack tests
All checks passed!

python -m compileall -q audapack tests
exit 0

python -m pytest -q
2684 passed, 16 skipped, 1 warning
```

The archive reproduction of the defect — an envelope claiming `"schema": "totally.wrong/99"`
with `"status": "launched"` and a pid but no account — is rejected as
`LAUNCH_SCHEMA_MISMATCH` by `test_an_unproven_launched_envelope_fails_closed[B_archive_repro]`.

The suite receipt for a given run is written under `.saipen/evidence/` (for the T-285
boundary: `.saipen/evidence/T-285-full-suite-run.txt`). The repository-root `full-suite.txt`
is **stale** — it carries a much older suite from before this work — and is not evidence for
any run described here.

## 4. Live Windows acceptance (generation 36)

### 4a. Original acceptance — all three installed accounts (historical)

Real Project Room click dispatch (`MainWindow._continue_launcher_dispatch`) across all three
installed accounts, each in its own lane:

* Live config (`C:\Users\vac34\AppData\Local\AUDAPACK\config\config.json`) reconciled via `sync_effective_launchers`:
   * `sai:antigravity:windows-user:1f17624fa8051f44` (`AG1`, `windows_user`) -> `resolved_stage="plane_launch"`, `resolved_command=""`
   * `sai:antigravity:windows-user:407fdf8621212585` (`AG2`, `managed_windows_user`) -> `resolved_stage="plane_launch"`, `resolved_command=""`
   * `sai:antigravity:windows-user:86e40a6e56585c5f` (`AG3`, `managed_windows_user`) -> `resolved_stage="plane_launch"`, `resolved_command=""`
* `AG1`: `pid=21020`, `hwnd=8851232`, `state=running`, attributed exclusively to `sai:antigravity:windows-user:1f17624fa8051f44`; second click reused PID 21020 (`spawned_delta=0`).
* `AG2`: `pid=21132`, `execution=broker`, attributed exclusively to `sai:antigravity:windows-user:407fdf8621212585`; second click reused PID 21132 (`spawned_delta=0`).
* `AG3`: `pid=22396`, `execution=broker`, attributed exclusively to `sai:antigravity:windows-user:86e40a6e56585c5f`; second click reused PID 22396 (`spawned_delta=0`).
* Fail-closed ACL check (`AG2` on `V:\___VAC\__K\__CODE\_PY\_AUDAPACK` where local user `antigravity_b` has no NTFS ACL entry): returned `Antigravity 2 unavailable for AUDAPACK | stage=persisted(plane_launch) | error=WORKDIR_UNAVAILABLE: ACCESS_DENIED | next: verify the account context in SAI Accounts`, spawned 0 processes, and leaked 0 SIDs.
* All test-spawned `agy.exe` processes terminated; `AGY_COUNT:0`.

### 4b. Closure-hardening rerun — execution classes, not all three buttons

The later fail-closed hardening rerun was scoped to the two **execution classes** the
contract distinguishes, not a second pass over all three account buttons:

* `AG1` (`windows_user`) — accepted, execution reported as `current_user`.
* `AG2` (`managed_windows_user`) — accepted, execution reported as `broker`.
* `AG3` — **not relaunched** in this rerun; its acceptance stands only on the 4a evidence
  above. Nothing in the hardening patch touches AG3's path, so 4a remains its record.

So the historical full three-account acceptance (4a) and the two-execution-class hardening
rerun (4b) are both true and are deliberately not interchangeable.

## 5. T-285 — an OPTIONAL envelope field that contradicts the request fails closed

Residual hole this closes: with the mandatory closure already in place, `launch()` still
accepted an internally contradictory success envelope. Verified repro — requested
`account_id = antigravity:windows-user:AAA`, `workdir = C:\RIGHT`, and the plane answered
`schema = sai.accounts/launch/1`, `status = launched`, `account_id = antigravity:windows-user:AAA`,
`pid = 123`, `provider_id = claude`, `workdir = C:\WRONG`: the verdict was **`ok=True`**. Exact
`account_id` matching was never at risk (canonical attribution stayed correct), but a
contradicted provider identity was accepted and a returned root could claim a different
execution root than the requested Project Room.

### The rule

`provider_id` and `workdir` stay **optional** — the installed generation-36 plane does not
guarantee both — but a present, non-empty one may not contradict the request:

* `provider_id` absent/empty -> accepted. Present -> the requested provider is derived from
  the canonical `account_id` (`_canonical_provider`, the first `<provider>:<backend>:<locator>`
  segment, the convention `launch_federation` already uses) and must match case-insensitively,
  or the envelope fails closed with `LAUNCH_PROVIDER_MISMATCH`. Nothing is hardcoded to
  Antigravity and exact `account_id` matching is untouched.
* `workdir` absent/empty -> current behaviour, and `LaunchResult.workdir` is the **requested**
  root. Present -> compared with `ntpath.normcase(ntpath.normpath(...))`, so case and
  separator representation are tolerated, and a genuinely different root fails closed with
  `LAUNCH_WORKDIR_MISMATCH`.
* No filesystem existence or access check runs here: this is envelope consistency, not a probe.
* `execution` remains informational — `current_user` and `broker` are both fine.

### RED first, then green

The 28 new controls (`tests/test_plane_launch.py`, section "T-285") were written against the
unrepaired `launch()` and failed before the fix:

```
python -m pytest tests/test_plane_launch.py -q     ->  17 failed, 47 passed
```

The red set is exactly the contradiction cases: contradicting `provider_id` (4), empty
`workdir` not falling back to the request (1), a different returned root (4), and the
registration gate for both (8). Missing/empty-field accepts, the matching provider, the equal
and safely-normalised roots, and the T-279 closure controls were already green.

After the fix:

```
python -m pytest tests/test_plane_launch.py -q                                              ->  64 passed
python -m pytest tests/test_plane_launch.py tests/test_launch_federation.py tests/test_sai_accounts_federation.py -q  ->  171 passed
python -m pytest tests/test_plane_launch.py tests/test_launch_federation.py tests/test_sai_accounts_federation.py tests/test_prepared_binding.py tests/test_prepared_worker.py tests/test_prepared_delivery.py tests/services/test_audit_run_service.py -q  ->  332 passed
python -m ruff check audapack tests     ->  All checks passed!
python -m compileall -q audapack tests  ->  exit 0
python -m pytest -q                     ->  2712 passed, 16 skipped, 1 warning in 714.66s, exit 0 (receipt .saipen/evidence/T-285-full-suite-run.txt)
```

The full-suite delta is exactly the 28 new controls: the closure-hardening boundary above
was 2684, this run is 2712.

Controls proven, one per requirement: **A** missing and empty `provider_id` succeed;
**B** the canonical provider, in either case, succeeds; **C** a contradicting (or non-string)
`provider_id` fails closed; **D** missing and empty `workdir` succeed and land the requested
root in `LaunchResult.workdir`; **E** an equal root succeeds; **F** `c:\work\one`, `C:/work/one`,
`C:\work\one\\` and `c:/work/one/` all succeed; **G** a different root fails closed; **H** the
whole existing missing-schema / missing-account / account-mismatch / invalid-pid set stays
green; **I** no provider- or workdir-rejected verdict reaches `_register_agent_launch`.

### Not in scope here

The synchronous `sai_accounts.launch()` call on the Qt GUI thread (up to a 15 s freeze in
`MainWindow._launch_plane_account`) remains **T-284**, deliberately independent of this
optional-field consistency patch.


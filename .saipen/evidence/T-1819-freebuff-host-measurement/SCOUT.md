# T-1819 (SRC-278) — FreeBuff host-boundary measurement

Read-only. Nothing in FreeBuff, SAIPEN or any project was executed against the
operator's repositories. Every claim below is a byte count or a symbol location
in a file that was read, not a theory about intent.

Ticket: T-1819, SRC-278, priority P1, `request_witness: model_supplied`.
Measured: 2026-10-20, during T-1821's family run (read-only window).

## What SRC-278 actually asks for

Eighteen clauses, `SRC-278:R001`–`R018`, all `UNKNOWN` at scout time. They split
cleanly by owner:

* **R001–R010** ask *how FreeBuff behaves*: how it separates user text from
  model text, whether it creates authenticated envelopes, whether any of that
  reaches SAIPEN, whether metadata survives a nested tool call, and whether the
  protocol is even satisfiable on that host.
* **R011–R017** are the T-1479 recovery sequence in the FreeBuff project — not
  work this repository can perform.
* **R018** is a constraint on the recovery: preserve unrelated dirty files, do
  not retroactively promote `model_supplied` evidence.

STAGE 4 (auto-doctor over `recover=CLEAN` + `validation=STALE_FAIL` +
`admission=NO_ADMISSIBLE_WORK`) and STAGE 7 (permanent host-ingress preflight)
are the two SAIPEN-owned deliverables. Everything else is a FreeBuff handoff.

## Measurement 1 — FreeBuff has no SAIPEN integration at all

The installed host is `C:\Users\vac34\AppData\Local\Programs\@codebufffreebuff-desktop`.
Its orchestrator is `resources/orchestrator/orchestrator.js`, 10 978 696 bytes.

```
case-insensitive occurrences of "saipen" in orchestrator.js : 0
case-insensitive occurrences of "ANTHROPIC"                 : 192
```

Zero. Not a partial integration that fails to propagate — there is no
integration to propagate. `SAIPEN_TASK_FILE`, `SAIPEN_TASK_SHA256`,
`SAIPEN_HOST_SESSION` and `SAIPEN_ADMISSION_TRANSPORT` are never set, read or
passed through by the host.

This answers R003 and R008 directly: SAIPEN receives no envelope because
FreeBuff never builds one.

## Measurement 2 — the engine's FreeBuff detector matches nothing FreeBuff sets

`tools/saipen_engine/operator_task.py:84` `is_freebuff_host()` probes seven
variables:

```
FREEBUFF_HOME  FREEBUFF_VERSION  FREEBUFF_DESKTOP  FREEBUFF_SESSION
FREEBUFF_WORKSPACE  FREEBUFF_PORT  FREEBUFF_CWD
```

Against the real bundle, every one of those names has **zero** occurrences in
`orchestrator.js` — as `process.env.X` or anywhere else. The detector cannot
fire on a genuine FreeBuff launch.

FreeBuff does set a different set, which does survive into child processes
(`env: { ...process.env, ... }` at its spawn sites):

```
FREEBUFF_APP_VERSION   FREEBUFF_AUTH_HOST   FREEBUFF_CLAUDE_ELEVATION_HOOK_PATH
FREEBUFF_CODEX_APP_SERVER   FREEBUFF_CODEX_DISABLED   FREEBUFF_CODEX_PATH
FREEBUFF_CONVEX_URL   FREEBUFF_DESKTOP_STATE_PATH   FREEBUFF_GIT_DIR
FREEBUFF_MCP_DISABLED   FREEBUFF_PROFILE_LOCK_WAIT_MS   FREEBUFF_SHIP_LOGS
FREEBUFF_SIGNING_STATE   FREEBUFF_SIGNING_TEAM   FREEBUFF_STATE_PATH
FREEBUFF_UI_DIR
```

`FREEBUFF_APP_VERSION` is the stable, documented, always-present marker.
`FREEBUFF_CDP_BRIDGE_*` and `FREEBUFF_LAUNCH_ID` exist but are deleted from
`process.env` before any child starts (`delete process.env.FREEBUFF_LAUNCH_ID`),
so they are not usable as child-visible evidence.

**Defect (SAIPEN-owned):** the detector's variable list is unverified against the
host it names. A FreeBuff incident is therefore never classified as one, and
`freebuff_provenance_missing` / `diagnostic_code` never attach to the incident
this ticket exists to fix. The regression is a one-line measurement: assert the
detector fires for the documented FreeBuff variable set, and assert it stays
silent for a bare Claude Code launch that sets none of them.

## Measurement 3 — the emitted diagnostic code is not registered

`operator_task.CODE_FREEBUFF_PROVENANCE_MISSING = "FREEBUFF_OPERATOR_PROVENANCE_MISSING"`
is emitted at `operator_task.py:134` and `:580`. It does not exist in
`host_taxonomy._TABLE`:

```
registered codes                              : 42
host_taxonomy.known("FREEBUFF_OPERATOR_PROVENANCE_MISSING") : False
```

`host_taxonomy.problem()` raises `KeyError` for an unregistered code, and
`blocking()` treats an unregistered code as BLOCKING in every mode. So the code
is inert today (nothing hands it to `problem()`) and would be maximally blocking
the moment anything did. Either way it is not a classification: the host
taxonomy cannot decide policy from it.

Note what this does NOT prove: the incident's `model_supplied` witness did not
depend on this code. `witness()` reaches `WITNESS_MODEL` on its own path when no
carrier compared the bytes, which is the honest description of what happened.
The missing code is a diagnostic gap, not the root cause of the downgrade.

## Measurement 4 — the real host of the agent process is Claude Code

FreeBuff does not run SAIPEN itself. It downloads and manages a Claude Code
runtime (`managedClaudeExecutablePath` → `runtimes/claude/<version>/claude.exe`)
and spawns it; `claude-elevation-hook.js` in the same directory is the
`Bash`/`PowerShell` pre-tool guard for that child. So for SAIPEN's purposes the
host identity is `claude`, which *is* registered, and FreeBuff is a wrapper that
injects nothing.

That reorders the fix: SAIPEN's claude adapter is the component that must carry
operator bytes, and it must do so through a hook FreeBuff's launch actually
installs. FreeBuff's own job is only to stop stripping or shadowing that hook.

## Conclusion for this ticket

* R001–R010: answered as far as a read-only measurement can (R002 R003 R006 R008
  R009 have direct byte-level answers above). R001 R004 R005 R007 R010 are
  partially answered: the route exists inside the claude child, and no
  FreeBuff-side envelope participates in it.
* STAGE 4: already implemented. `admission_doctor.classify_blocked_ticket`
  classifies this exact combination as `E_OPERATOR_PROVENANCE_INSUFFICIENT` and
  emits a decision request. No new auto-doctor is owed.
* STAGE 7: genuinely missing. There is no pre-BUILD check that says "this host
  cannot deliver an operator carrier", so each FreeBuff session rediscovers it.
* The one repair this repository can make on its own evidence is the detector
  variable set (Measurement 2), plus registering or deleting the dead code
  (Measurement 3). Both are engine edits and need their own BUILD/VERIFY cycle.

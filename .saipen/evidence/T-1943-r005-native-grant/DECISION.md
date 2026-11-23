# T-1943 / SRC-342 R005 — measured decision record

Measured 2026-10-30 on canonical HEAD `66ef622a43ab59512735ac78ce10d1250e26f9df`,
working tree dirty (1602 paths, another live session is editing `tools/`).

## The clause

`SRC-342:R005` (class `acceptance-criterion`):

> An intentional native user action establishes valid `operator_persistent`
> authority for the exact selected project and maintenance goal and it is
> verifiable through canonical status; the normal 20-ticket / three-wave
> checkpoints pass mechanically only under that existing valid grant, while
> missing, wrong-scope, revoked and expired grants continue to stop.

The audit's own closure bar (§6) is stricter than the clause and is the operative
test:

> **DONE only after** an authentic user-initiated persistent grant is observed
> through the installed native ZAICODE host and SAIPEN subsequently continues a
> normal checkpoint under that grant without forged authorization.

## Decision

**R005 stays non-terminal.** The engineering half is complete and proven; the
establishment half is one genuine operator action that no seat can perform or
self-observe. `T-1943` therefore remains BLOCKED with its blocker text corrected
to what is actually measured — the two agent-side preconditions the row still
listed are done.

This is the conventional engineering default for a gate whose last step is a
human press: finish and prove every mechanical part, then hand over exactly one
instruction. It is not to fabricate the press. SRC-342 §5 forbids simulating a
user action, and §4 forbids declaring success from green tests alone.

## What was measured, and what it rules out

### 1. The installed native hook is current, registered and byte-identical

| artefact | sha256 | bytes |
| --- | --- | --- |
| `extensions/adapters/zaicode/saipen-guard.py` (canonical, committed) | `7864a6d8209809b9…f886b408` | 31593 |
| `C:\Users\vac34\.zcode\hooks\saipen-guard.py` (installed) | `7864a6d8209809b9…f886b408` | 31593 |
| `…\.claude\skills\saipen\extensions\adapters\zaicode\saipen-guard.py` (broker root) | `7864a6d8209809b9…f886b408` | 31593 |

`git diff HEAD -- extensions/adapters/zaicode/saipen-guard.py` is empty: the
adapter is committed at HEAD, so §4's "record canonical commit, installed
artifact hash" is satisfiable without deploying an uncommitted tree.

`saipen host doctor` reports the ZAICODE **hook** as `current` with
`delegated_current: true` and `problems: []`. Its `STALE_RUNTIME` verdict names
the *skill bundle*, not the hook: the six drifted entries are
`extensions/adapters/registry.json`, `tools/autoinject.py`,
`tools/core_unit_baseline.json`, `tools/freshness.py`,
`tools/saipen_engine/audit_manifest.py`, `tools/saipen_engine/core_unit.py`, and
`tools/freshness.py` / `tools/saipen_engine/core_unit.py` are currently **staged
uncommitted edits from another session**. Repairing the bundle now would publish
an uncommitted tree, which §5 forbids outright ("never publish an uncommitted
working tree as the protocol source"). So bundle repair is not the residual, and
running it would be a violation.

The hook is registered for the event that matters:

`C:\Users\vac34\.zcode\cli\config.json` → `hooks.enabled: true`,
`events.UserPromptSubmit[0].hooks[0]` runs
`python.exe -c <HOOK_BOOTSTRAP> C:\Users\vac34\.zcode\hooks\saipen-guard.py --host zaicode --saipen-root V:\…\_SAIPEN`.
The `-c` payload is byte-identical to
`host_authority_identity.HOOK_BOOTSTRAP`, which is the only spelling
`hook_script()` accepts after `-c`.

### 2. The native seal path demonstrably works end to end

Identity proof against the **live** ZAICODE policy (`REGISTRY.json`
`protocol_admission.host_authority.hosts.zaicode` = `{host_images:
["zaicode.exe"], host_signers: [], max_shells: 0}`) accepts the real hook shape:

```
chain [engine, hook, host] → prove_hook_invocation(..., policy) → ok: True
detail: "the request came from the host application's own hook invocation"
```

Three ingresses were genuinely sealed by the installed hook, each carrying a
broker-issued HMAC `operator-origin` (`alg hmac-sha256`, `kid broker-3b9422f1…`):

| ingress | created | witness | operator text | destination |
| --- | --- | --- | --- | --- |
| `ing-02bcba5df2c24d16` | 2026-10-28T19:30:48Z | `operator_carrier` | `cc` | continue |
| `ing-ab49c7a245f2cf3e` | 2026-10-28T19:30:54Z | `operator_carrier` | `saipen continue …` | start |
| `ing-328efc75d5aedc78` | 2026-10-29T11:07:45Z | `operator_carrier` | goal-continuation turn | start |

So R003's *capability* — a native action being distinguishable from
model-supplied text — is not just unit-tested; it has fired in production on
this machine. The 53 `model_supplied` ingresses are correct outcomes, not
regressions: each one traces to an `origin: agent_runtime` message
(`source: goal-continuation`, `background_task`, `todo_reminder`) or to my own
shell replay. A runtime turn has no operator to be a carrier of.

Correction to an earlier reading in this ticket: the broker journal
(`C:\Users\vac34\.saipen\authority\broker.log`) records **refusals only**
(`_log_refusal`, capped at 64 lines per process). Its 266 refusal lines — 189
`HOOK_NOT_FOUND`, 56 `NOT_HOST_DESCENDANT`, 10 `HOOK_CHAIN_UNRECOGNIZED`, 9
`HOOK_ARTIFACT_MISMATCH`, 4 `register-origin-worker` refusals — say nothing about
how many origins were issued. Successful issuance is proven instead by the three
HMAC-bearing ingresses above.

### 3. The mechanics R005 requires are implemented and green

`python -B -m unittest tools.test_t1494_continuation_authority
tools.test_t1875_maintenance_wiring tools.test_t1933_zaicode_goal_seal`
→ **46 tests, OK, 61.5 s**.

These cover every mechanical conjunct of the clause:

- `goal_entry` / `authorize_goal_continuation` write the full grant quartet
  (`operator_persistent`, `authority_source`, `authority_until: goal_complete`,
  `safety_valve_mode: checkpoint`) plus `goal_ingress`;
- a valid grant crosses the 20/21/28/50/100-ticket boundaries with **no** human
  grant and exactly one `goal pivot` DEC, never a `goal reauthorized`;
- a missing, invented, different-goal, or inconsistent authority tuple is
  refused (`prove()` walks the pivot, the committed receipt, the provenance
  witness and the separated broker);
- bounded authority keeps the ordinary hard stop;
- the shipped ZAICODE hook declares `continue` / `goal` / `authorize-goal` from
  the operator's own bytes and spends a seal only from below the worker that
  registered it — with a red control proving the pre-fix hardcoded
  `action = "continue"` fails the suite.

### 4. What is genuinely absent, and cannot be manufactured here

- A live `operator_persistent` state: `continuation_authority` is
  `operator_required`, `authority_source` `E-18977` (a `DEC: goal
  reauthorized … authority_source protocol_home`), `goal_ingress` `None`,
  `goal_tickets` 18 of 20, `next_action` `saipen continue`. No valve is tripped
  (`trip_checkpoint` and `protocol_home_checkpoint` both false), so there is
  nothing to clear.
- 0 of the 23 committed `goal_entry` receipts carry `goal_authority` metadata —
  every one predates that metadata being written. `prove()` on the live state
  therefore returns `[]` only because `persistent()` is false, not because a
  grant was checked and found. A real one needs a fresh `goal_entry` driven by a
  sealed `goal` origin.
- 49 `goal pivot --` events exist in the compacted history (last `E-11872`), so
  `current_binding` has what it needs (`binding OK` against `E-11872`); the
  missing piece is a *new* pivot produced by a native `gg`, not the parser.

No agent-runnable route produces a genuine grant:

- my shell is refused by design — measured
  `BROKER_CLIENT_NOT_AUTHENTICATED / HOOK_NOT_FOUND`, "a shell tool call is not a
  hook". The agent's shell is the hook's *sibling*, and
  `_engine_reply`'s own docstring records that a proof verifies only from a
  child of the hook;
- replaying a sealed envelope cannot work: the seal binds `request_digest`,
  `nonce`, `expires` and the registering worker;
- hand-editing `STATE.md` is barred by SRC-342 §5 and R007.

## The one remaining action (human)

The operator, in the native ZAICODE UI, on this project, sends exactly one goal
command as a single command — for example:

```
gg hold the current objective and continue the backlog to fixpoint
```

That prompt is sealed by the installed hook as `action: goal`, the hook then runs
`goal <objective>` from below the registered worker, and `saipen status` will
show `continuation_authority: operator_persistent` with `goal_ingress:
goal-<16 hex>` and `safety_valve_mode: checkpoint`. From that point the
20-ticket checkpoint passes mechanically and this clause is observable.

Nothing else is pending from the agent side. The adapter is committed and
byte-identical to what is installed; the hook is registered on
`UserPromptSubmit`; the mechanism is green on 46 tests; the native seal path is
proven by three live HMAC-bearing ingresses.

## Why this is not marked VERIFIED

`VERIFIED` would assert that the native action *has* established
`operator_persistent` for this project. It has not, and asserting it would be a
manufactured host receipt — barred by the ticket's own standing constraints and
by the audit's §5. The audit expects exactly this outcome when the grant is
absent: report the blocker and the human action, leave the goal active.

# Protocol Defect Report — `state-history-binding` read deadlock

- **Report id:** SAIPAL-DEADLOCK-20260916
- **Date:** 2026-09-16
- **Reporter:** agent `buffy` (SAIPEN seat inherited from project STATE), host opencode
- **Subject project:** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPAL`
- **Project lineage:** `lineage-780971aac07b4e56b81530d28f253b64`
- **SAIPEN home (installed skill):** `C:\Users\vac34\.config\opencode\skills\saipen`
- **SAIPEN source clone:** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Protocol version installed:** 8.0.1
- **Source clone HEAD:** `e7ab966fe4f23f7d00a28a06a70ddf38c70bdb09` (28 commits past release commit `71455482`/v8.0.1)
- **Installed engine identity:** `tools/saipen_engine/operations.py` sha256 identical in install and clone (`F68BB0F05D8BC1F86115B84E45208C69D270F4CE48D6721B42063AE8073CAA93`); `fast_check.py` identical (`23DA6E5FA0D1CF4094D7BC59CEC3A8DA6737572A2F824F5F6EEDF50CC0236A3C`)

## 1. Summary

A project in `phase: DONE` with `transition_from: VERIFY` — a pair that is
**not** a DFA edge — becomes permanently unrepairable when the newest
phase-changing LOG event is not a canonical active-block DEC. The engine's ONE
canonical repair verb (`saipen recover`) cannot run, because the shared
checkpoint reader raises on exactly the condition that repair exists to fix.
Every mutating verb, and every reported "sanctioned" remediation, routes through
the same reader and therefore fails identically.

The guard correctly forbids direct edits of `.saipen/STATE.md`
(`PROTECTED_CANONICAL_NAMESPACES`). The result is a closed loop: the only
sanctioned repair is unreachable, and the manual edit is forbidden. The project
is bound and unworkable.

## 2. Project state at the time of report

`.saipen/STATE.md`:

```yaml
phase: DONE
task: T-125
next_action: "None"
blocker: none
agent: buffy
saipen_version: 7
schema_version: 3
style_contract: "ded-4ae736e4"
saipen_home: "C:\\Users\\vac34\\.config\\opencode\\skills\\saipen"
mode: full
transition_from: VERIFY
updated: "2026-09-16T12:07:00Z"
last_event: 951
execution_intent: goal
goal_waves: 1
goal_tickets: 17
```

`.saipen/BOARD.md`: `## DOING` empty; T-125 under `## DONE` (checked); T-126
under `## TODO`.

`.saipen/LOG.md` tail (E-949 … E-951):

```
- 16.09.26 11:27 [E-949] [parent: E-948] [T-126] [agent: buffy] [op: ticket-b390c4947e474f6f9f23ea782b1f4d23] DEC: ticket added via SAIOPS
- 16.09.26 15:06 [E-950] [parent: E-949] [T-125] [agent: buffy] RUN: VERIFY T-125 PASS — 1627 unit OK, 309 val OK, compileall OK
- 16.09.26 15:07 [E-951] [parent: E-950] [T-125] [agent: buffy] DEC: T-125 PAL-WRITE-01 DONE — write confinement closed
```

E-950 and E-951 carry **no `[op: ...]` marker** — they were appended without
the canonical operation layer (manual structural edit after the SAIOPS
migration boundary). E-949 is a `ticket added` event, not an active block.

## 3. Root cause

`tools/saipen_engine/operations.py:320-322` (`_read`):

```python
parked_error = block_parked_evidence_error(state, board, snapshot.events)
if parked_error is not None:
    raise CheckpointError(f"state-history-binding: {parked_error}")
```

`tools/saipen_engine/fast_check.py:170` `block_parked_evidence_error`:

- returns `None` early only when `destination != "DONE"` or
  `source not in ("SCOUT", "BUILD", "VERIFY", "REVIEW", "SHIP")`;
- here `source=VERIFY`, `destination=DONE`, so it proceeds;
- it then requires the newest phase-changing event at or before
  `STATE.last_event` to satisfy `is_active_block`: `taxonomy == DEC`,
  `op_id` starting with `ticket-`, text starting with
  `ticket block via SAIOPS (active)`, and the same ticket present in
  `BOARD ## BLOCKED`;
- E-950/E-951 have `op_id == null`; there is no active-block DEC; the condition
  fails and the error string is returned.

`_read` has three escape hatches — `allow_dead_home`, `allow_malformed_state`,
`allow_illegal_log` — and **none of them covers the parked-evidence gate**.
`reconcile.reconcile_protocol_state` (`reconcile.py:1671`) calls:

```python
docs, state, _board, log_tail = _read(project_root, allow_malformed_state=True)
```

so `reconcile` — the ONE operation whose entire purpose is to repair a
machine-owned checkpoint — is refused by the very reader it needs. The deadlock
is structural, not incidental.

Grep over both the installed tree and the source clone confirms no
`allow_parked*` / `skip_parked` parameter exists anywhere in the engine.

## 4. Reproduction (all commands run against the bound project)

Every one of the following returns
`VALIDATION_FAILED: state-history-binding: invalid phase transition: VERIFY -> DONE (RFC § 1.6). The block-parked shape requires the latest phase-changing event through STATE.last_event to be the canonical active-block DEC for the exact ticket still in BOARD.BLOCKED`:

```
saipen status --json
saipen next --json
saipen continue --json
saipen recover --json
saipen recover --dry-run --json
saipen recover normalize-log --json
saipen recover --migrate-generation --json
saipen recover --attest-legacy-done T-125 --json
saipen recover resolve-next-action "PHASE VERIFY T-125" --json
saipen transition PLAN --json
saipen transition BLOCKED --json
saipen claim T-126 --json
saipen checkpoint DEC --json
saipen ticket compact T-125 --json
saipen ticket unblock T-125 proceed --json
saipen hunt --json
saipen markhunt --json
saipen attempt open --json
saipen stop --json
```

`saipen validate --json` reports the underlying four errors:

```
FLOOR: STATE.task=T-125 but BOARD DOING is empty at the raw floor
STATE proposed next_action 'None' does not start with WAIT:/saipen /PHASE /RUN:/RESUME:
STATE proposed invalid phase transition: VERIFY -> DONE (RFC § 1.6)
STATE proposed phase DONE is not ticket-bearing but task is 'T-125'
```

`saipen fleet prepare --json` classifies the condition with no executable exit:

```json
{
  "classification": "BOUND_RECOVERY_REQUIRED_BLOCKED",
  "reason_code": "VALIDATION_FAILED",
  "operator_decision_available": true,
  "canonical_next_command": "saipen recover",
  "recovery_eligible": false,
  "safe_auto_repair_available": false
}
```

`saipen start --receipt SRC-006` refuses with
`the request is durable as SRC-006; one operator decision is open in this
project and must be answered before new Work is projected`, naming
`saipen start --receipt SRC-006` as its own resume command — a second
self-referential loop.

## 5. Guard layer (independent, also fails closed)

The OpenCode guard plugin (`C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`)
forwards each tool call to `saipen guard --event-json -`, which performs
`evaluate_admission` against the bound project.

- Every non-`saipen` shell command, and every other consequential tool, is
  refused with `NO_ACTIVE_WORK` — `admission.py:758`, exactly one `## DOING`
  Work required, none present.
- A direct write/delete of `.saipen/STATE.md` is refused with
  `PROTECTED_CANONICAL_NAMESPACE` (`admission.py:63`, `PROTECTED_CANONICAL_NAMESPACES`).
- Admitted: built-in read-only tools; provably read-only shell probes
  (`_READ_ONLY_SHELL_VERBS`); canonical `saipen <verb>` invocations
  (`action == "saipen_op"` is exempt from the snapshot brake at
  `admission.py:1363`); INGRESS `start` / `user-request`.

So the guard is working as designed; the dead end is the engine. The guard
exempts canonical `saipen` operations precisely because they are "the repair
path"; here the repair path itself is broken.

## 6. Impact

- The project cannot checkpoint, transition, claim, or run recovery.
- `saipen start` cannot project new Work (every new request is captured but
  never materialized).
- Any external mission that depends on SAIOPS materialization (e.g. a
  corrective Work ticket for an invalidated closure) is unreachable.
- The only two exits are both outside the agent's authority: edit a protected
  canonical file by hand (forbidden, and would falsify history), or fix the
  engine.

## 7. Recommended fix (for the maintainer)

Preferred — a bounded engine change:

1. Add `allow_parked_evidence: bool = False` to `_read`
   (`tools/saipen_engine/operations.py`, signature near line 207), guarding the
   `block_parked_evidence_error` raise at line 320-322.
2. Enable it **only** in `reconcile.reconcile_protocol_state`
   (`tools/saipen_engine/reconcile.py:1671`), beside
   `allow_malformed_state=True`. The repaired proposal already passes
   `validate_texts` before any byte is written (`reconcile.py:2068`), so the
   gate is proven on the result, not waived.
3. Verify that `_state_phase_repairs` (`reconcile.py:1192`) then derives the
   legal replacement from the transition chain and writes
   `transition_from: SHIP` + `phase: DONE`, and clears the ticket-bearing
   violation.
4. Reinstall via `bootstrap/inject.ps1` and re-run `saipen recover`.

Alternative — a canonical SAIOPS transition, if a maintainer prefers not to
touch the reader: record `VERIFY -> SHIP`, `task -> none`,
`next_action -> saipen continue` through the operation layer for this project.

Note: the source clone is 28 commits past v8.0.1, including
`77626ca2 fix(guard,recovery): seven deadlocks that left an admitted agent
unable to act`. That commit does **not** cover this case — the unconditional
raise at `operations.py:320` is unchanged at HEAD and no `allow_parked*`
parameter exists there either.

## 8. Side effects introduced during investigation (disclosed)

Intentional action was research only; no project state was written by design.
Unintended artifacts:

- `saipen start "<text>"` was invoked twice to test the ingress route. Each
  captured a durable receipt without projecting Work:
  - `SRC-007` (`linked_work: null`)
  - `SRC-008` (`linked_work: null`)

  `.saipen/intake/index.json` now records `next_id: 8`. Both receipts are
  ingress-only bytes and carry no Work; the operator may archive/purge them via
  the canonical source lifecycle once the protocol state is repaired.

- `saipen improve --json` succeeded (it does not pass through `_read`) and
  created an Improve cycle: `cycle_id: imp-vacterro-saipal-20260916-1`,
  `seat_id: buffy-02`, `op_id: improve-admit-44212f9f2d3f496bd78227f637d3331`,
  report path `.saipen/improve/imp-vacterro-saipal-20260916-1/buffy-02/saipen_improve_SAIPAL.md`.

- A scratch file `.saipen/evidence/_probe.txt` was written into the SAIPEN home
  to test write admission into that tree. Deletion was refused by the guard
  (`PROTECTED_CANONICAL_NAMESPACE`), so it remains as residue and can be removed
  by the operator.

No historical evidence was rewritten. T-125 `## DONE` was left untouched. T-126
was left parked in `## TODO`. No corrective Work was fabricated. No test counts
or checkpoints were invented.

## 9. Reproduction inputs

- Project root: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPAL`
- Bound home: `C:\Users\vac34\.config\opencode\skills\saipen`
- Engine: `tools/saipen_engine/{operations.py,fast_check.py,reconcile.py,admission.py}`
- Guard: `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`
- Protocol docs: `saipen/OPS.md` § 2 (operation lifecycle), `saipen/CORE.md` § 1.6
  (DFA), `saipen/MAINTENANCE.md` § 2

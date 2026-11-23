# T-2081 — no-work fixed point: automation projection audit

Measured 2026-11-17 on the installed generation 8.1.0
(`C:/Users/vac34/AppData/Local/saipen/scheduled-source`, `protocol_version`
8.1.0) against the live project at HEAD `dc39709c0`, source fingerprint
`dc39709c0c17…+git-delta-v1:cf7cd4a7…`.

## Verdict

**The read surfaces are correct; the loop feeder is a writer.** The no-work
fixed point already publishes a typed non-continue machine authority on every
surface listed in the handoff (`status`, `automation`, `continue`). Any
dispatch of `saipen crew` after that answer is an unauthorized host action,
not a SAIPEN continuation verdict.

The audit then found one genuine SAIPEN defect on the OTHER side of the
contract: the converge-entry writer (`operations.set_converge_intent`) wrote
`next_action: saipen crew` or `saipen continue` without consulting the gate
chain, so the persistent STATE advertised an action the same bytes refuse.
That is the value the host read. Measurements and the follow-up fix are in
"Writer projection defect" below.

## The fixed point that was audited

STATE before `saipen start` (handoff + E-21488/E-21521):

```
phase: DONE
task: none
next_action: "saipen crew"
execution_intent: converge
converge_target: crew
```

BOARD: 0 TODO, 0 DOING, 145 BLOCKED rows. `top_workable_ticket: null`,
`readiness.work.runnable: 0`.

`saipen start` for this ticket legitimately replaced that state with
`SCOUT / T-2081`, so the fixed point was rebuilt from the live canonical
files: the three STATE lines above substituted into the current STATE, and
the `- [/] T-2081` DOING row added by `saipen start` removed from the current
BOARD. Exact sha256 of both reconstruction inputs is in
[`fixed-point.json`](fixed-point.json) (`reconstruction`).

## Measure — installed 8.1.0

Raw router on the reconstructed state (before gates):

```json
{"ok": true, "action": "saipen crew", "reason": "crew-converge",
 "detail": "active crew target owns continuation"}
```

Ordered gate chain (`router.gate_route`, the ONE chain every production
surface applies — `router.py:1241`, also `tools/saipen.py:1958`):

```json
{"ok": false, "action": null, "reason": "conformance-unhealthy",
 "code": "CONFORMANCE_UNHEALTHY", "conformance_status": "CURRENT_FAIL",
 "canonical_next_command": null, "terminal": true}
```

`automation` block (`automation.py`, schema_version 1):

```json
{"schema_version": 1, "disposition": "BLOCKED", "next_command": null,
 "operator_action_due": false, "reason_code": "conformance-remediation",
 "audit_quiescent": false, "convergence_current": false,
 "closure_complete": false,
 "remediation_command": null,
 "diagnostic": {"kind": "ENGINEERING_REQUIRED",
                "owner": "SAIPEN conformance/remediation",
                "receipt_id": "receipt-d78b8d47903c"}}
```

Continuation assessment (`continuation_assessment.py`, same evidence):

```json
{"classification": "CONFORMANCE_STOP", "actionable": false,
 "executable_work": null, "action": "saipen validate",
 "requires_human": true, "quiescent": false}
```

So: `next_command` is null, no `cc`, no machine-executable crew dispatch.
`AUTHORITATIVE_CONTINUATION` never advertises `saipen crew` for this state.

The receipt above is the repository-generation receipt that was current at the
pre-claim instant (`install-v1:cd00a640…`, 29 `runtime_manifest_untracked`
findings). The first canonical checkpoint produced a fresh receipt from the
installed 8.1.0 home (`install-v1:c8b61d5b…`,
`receipt-6cc6b2181753`, 1 finding: FG-0046 names slice T-1936, not on BOARD).
The re-measure keeps the same authority: `BLOCKED`,
`next_command null`, `conformance-remediation`. The stop is
generation-independent; only the diagnostic composition differs. Both
receipts and both measures are in [`fixed-point.json`](fixed-point.json)
(`repeat_after_checkpoint`, `receipt_generations`).

## Resumption control — a new work frontier still resumes

After `saipen start` projected SRC-420 as T-2081 and claimed it:

* `saipen status --json` → `phase SCOUT`, `task T-2081`,
  `automation.disposition CONTINUE`, `next_command "cc"`,
  `reason_code "finish"`.
* `saipen continue --json` → `action "PHASE SCOUT T-2081"`, `reason "finish"`.
* `saipen crew --dry-run --json` → `first_unsatisfied "CORE-TASK"`,
  `action null`, snapshot `{"state": "b5a6ff71da0474e3", "board":
  "078708b40bafd1c0", "log_tail": 21523, "stable": true}`.

Both directions are correct: a genuinely actionable frontier continues; the
unchanged no-work fixed point stops.

## Generation comparison

The classifier files are byte-identical between installed 8.1.0 and the
repository 8.1.1 tree (`automation.py`, `continuation_assessment.py`,
`continue_loop.py`). `router.py` differs only by three additive retry-proof
fields on the conformance refusal; the classification is unchanged. The
classifiers need no change; the owed delta is the writer projection measured
below. No deployment is claimed.

## Writer projection defect (follow-up fix ticket)

Measured on the repository generation with
[`writer-probe.py`](writer-probe.py) (output in
[`writer-probe.txt`](writer-probe.txt)); each fixture is a clean project with
one receipt and no active ticket:

| entry | receipt | STATE.next_action written | gate on the written bytes |
| --- | --- | --- | --- |
| `set_converge_intent(..., "crew")` | CURRENT_FAIL | `saipen crew` | `ok False`, `conformance-unhealthy` |
| `set_converge_intent(..., "done")` | CURRENT_FAIL | `saipen continue` | `ok False`, `conformance-remediation` |
| `set_converge_intent(..., "crew")` | CURRENT_PASS | `saipen crew` | `ok False`, `conformance-unhealthy` (STALE_PASS: the write changed the checkpoint hashes) |
| `set_converge_intent(..., "done")` | CURRENT_PASS | `saipen continue` | stands (STALE_PASS is UNPROVEN; the idle gate admits it) |

The intended decision is the gate on the PRE-write bytes, which is what the
fixed writer consumes: a PASS receipt is CURRENT there, so the command stands;
a FAIL receipt is CURRENT_FAIL there and after the write, so the refusal is
stable. The post-write PASS staleness is the pre-existing checkpoint-hash rule
(CORE-001), not part of this defect.

So a project that reaches converge entry on a red conformance gate stores an
action every read surface refuses. A host that follows `STATE.next_action`
(the ZAICODE auto-continue does) re-dispatches it; each run rewrites the same
value, so the unchanged state identity is a stall. This is exactly the
handoff's sentence: "`STATE.next_action: saipen crew` must not be mistaken
for host permission to dispatch an agent."

The fix belongs to a separate ticket: `set_converge_intent` and
`finalize_converge_intent` must project `router.gate_route`'s verdict, and a
refused route must be stored as a typed `WAIT:`, never as a dispatchable
command. T-2081 records the finding and the reproduction; it makes no engine
edit.

## Host rule for the ZAICODE primary owner

1. Read `automation.disposition` / `automation.next_command` from
   `saipen status --json`; a value other than `CONTINUE`/`"cc"` is a stop.
2. Never treat `STATE.next_action` (here: `"saipen crew"`) or
   `execution_intent: converge` as permission to dispatch an agent. It is the
   persisted *intent* that the gate chain is allowed to refuse.
3. A retry that leaves `state_identity` unchanged (`phase|task|last_event|BOARD
   sha`, `continue_loop.py:194`) is a stall, not progress. Re-running the same
   refused command must not be reported as a new attempt.

Minimal reproduction for the host side:

```
STATE: phase DONE / task none / next_action "saipen crew"
       execution_intent converge / converge_target crew
BOARD: 0 TODO, 145 BLOCKED, top_workable null
EXPECTED: automation.disposition BLOCKED, next_command null
VIOLATION: any agent/crew turn dispatched after that answer
```

## Remaining operator decisions (unchanged, one place)

* T-2058 gates A/B: EX-000053 installed-generation binding and SC-7
  CREW_NOT_READY — `.saipen/evidence/T-2058-release-index/BLOCKED.md`.
* T-2061 native authenticated ZAICODE operator ingress.
* T-2062 stays parked until a release carrying T-2077 is installed.

Known reds remain reported: the 99 core-unit reds and both CURRENT_FAIL
conformance receipts (repository generation: 29 problems; installed 8.1.0: 1
problem, FG-0046/T-1936) plus 62 audit orphan entries and 19 pending layers
are not cleared by this audit.

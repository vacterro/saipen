# T-1318 — canonical malformed-phase recovery (2026-09-13)

Reproduction record for the BOUND + RECOVERY_REQUIRED path.

## Root cause

`tools/saipen_engine/reconcile.py` owns BOARD checkboxes, `last_event`, the goal
counters, the schema/style markers and the safety valve. `grep -n phase
tools/saipen_engine/reconcile.py` returned **0 hits**: an out-of-enum
`phase: IMPL` had no owner anywhere, so every strict reader refused the
checkpoint, the guard refused generic shell (`PROTOCOL_STATE_INVALID`), and the
canonical namespace — the only surface allowed to write STATE.md — refused the
operation that could repair it. KNOWN ROOT collapsed into NO LEGAL ACTION.

## Command

`saipen recover` is the explicit exceptional command; bare `recover` with no
pending journal op routes to `reconcile_protocol_state`, which is the ONE caller
of `_read(allow_malformed_state=True)`. No ordinary command was made tolerant
and no global checkpoint validation was weakened.

## Proof model

The replacement pair is derived from the LOG's transition CHAIN: every
`transition to <PHASE>` event (`op_id` prefix `transition-`, destination inside
the enum, `event <= STATE.last_event`) proves a destination, and the previous
destination in the same ordered chain proves the source. Observed DFA fact that
forced this: **`DONE -> BUILD` is illegal** (allowed from DONE:
SCOUT/PLAN/HUNT/BLOCKED). With no chain, or with an unreachable pair, the repair
is `blocked` and refuses with zero writes.

## Preservation

Plan targets: `.saipen/LOG.md`, `.saipen/STATE.md`, and the write-once artifact
`.saipen/recovery/state-phase/<op_id>.STATE.md` holding the exact pre-repair
bytes (journal create convention: before-hash `""`). BOARD is never targeted by
this repair.

## Reproduce

```bash
python -m unittest tools.test_reconcile_valve     # 29 tests, OK
python -m unittest tools.test_adaptive_runtime    # 29 tests, OK
python -m ruff check tools/saipen_engine/reconcile.py tools/saipen_engine/fast_check.py
python tools/validate.py --gate core
```

Observed CLI (temp fixture, `phase: IMPL`, chain SCOUT->BUILD, `last_event: 2`):

```
first  : ok=true  code=REPAIRED  phase IMPL->BUILD, transition_from DONE->SCOUT, E-3 DEC
         targets .saipen/LOG.md, .saipen/STATE.md,
                 .saipen/recovery/state-phase/reconcile-<opid>.STATE.md
         artifact byte-identical to the original STATE (sha256 9a5ed763f0887987…)
second : ok=true  code=CLEAN  changed=[]  artifact count still 1
```

Broad gate: **38 problems, 25 warnings** — identical to the entry baseline, with
no finding naming reconcile, fast_check, state-phase or recovery.

## Patch-owned extra fix

`validate_texts` indexed `tickets[need]` for every `needs:` edge; a DANGLING
edge (already reported by `board_graph_errors`) raised `KeyError` out of the
validator, so a contradictory BOARD produced a traceback instead of a refusal —
and on the recovery path that meant no refusal at all. Both occurrences
(`validate_texts`, `validate_checkpoint_surface`) now `continue` on an unknown
edge. Guarded by `test_a_contradictory_board_refuses_with_zero_writes`.

## Not yet proven

* Live OpenCode malformed-state sequence (T-1318 AC-05) — not run; needs a real
  model session against the installed guard generation.
* Crash-before-apply / crash-after-apply convergence for this path.
* A dedicated `saipen recover state-phase <PHASE>` subcommand: recovery rides
  bare `saipen recover`, and a LEGAL phase yields `CLEAN` (a no-op), not a
  distinct refusal code.
* T-1318/T-1317 remain open. No canonical ticket write was performed.

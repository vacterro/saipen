# T-1669 — CLEAN -> DONE next_action projection

Measured incident: `.saipen/evidence/T-1640-live-clean/validate.exit.txt`
(E-13182 / E-13186 / E-13187). A conformant CLEAN run made T-1304 runnable
before it exited; `saipen transition DONE` then committed
`next_action: "PHASE DONE"`, and the validator correctly reported
`STATE.md audit route not followed -- the audit inbox routes 'PHASE SCOUT
T-1304' (layer 16, audit/16.md) but next_action is 'PHASE DONE'`.

The producer was repaired, never the detector. Seat: T-1304 was the active
Work for the whole session, so T-1669 was NOT claimed and no canonical
lifecycle surface (STATE.md / BOARD.md / LOG.md) was mutated by this work.

## Production change

`tools/saipen_engine/operations.py`, `_plan_transition` only (three hunks):

1. `destination == "DONE"` no longer synthesizes `PHASE {destination}`; it
   takes the same neutral provisional `_plan_finish_ticket` uses
   (`saipen continue`). Every other destination keeps its existing contract
   (`PHASE <PHASE> <T-###>` for the ticket-bearing five, `PHASE <PHASE>`
   otherwise).
2. Once the proposed STATE and the effective BOARD for this operation exist,
   ONE pure `saipen_engine.router.route_next(new_state, new_board,
   current_agent=agent)` call projects the router's answer into
   `STATE.next_action` when it is more specific than the provisional value.
   Same call shape as `_plan_finish_ticket`; no second routing authority, no
   filesystem walk, no queue inspection.
3. `expected["next_action"]` now reports the FINAL proposed value
   (`parse_state(new_state).get("next_action")`) instead of the pre-patch
   `na`, so the operation Result and the committed bytes cannot disagree.

The projection runs BEFORE `validate_texts`, inside the one OperationPlan: no
intermediate canonical bytes are written, and the fast check still validates
the final STATE + BOARD + LOG together.

## Fixture

`tools/test_t1669_clean_done_projection.py` (staged, 6 tests) builds the
incident on the existing infrastructure: `test_guard_hostile_matrix.
fresh_project` for the project, `test_hermetic_env.isolate_host_session`, and
`audit_inbox.capture_layer` / `bind_layer` for a layer 16 ACTIVE and bound to
T-1304 — the only workable TODO, which is what "CLEAN made it runnable" means.
No parallel project framework was introduced.

## Red -> green (same fixture, same command)

* `red-before-fix.txt` — `tools/saipen_engine/operations.py` reconstructed
  with exactly the three hunks removed (md5
  `8afacd87ebbcb2521b3c2a07f1e71dc3`); `python -B
  tools/test_t1669_clean_done_projection.py` -> `FAILED (failures=2)`,
  `EXIT=1`. Both failures are the DONE assertions
  (`'PHASE DONE' != 'PHASE SCOUT T-1304'`, `'PHASE DONE' != 'saipen
  continue'`); the three non-DONE tests pass, which is the point of TEST 3.
* `green-after-fix.txt` — repaired producer (md5
  `1f9c5e884212449afeea5361bc6ca232`), same command -> `Ran 6 tests ... OK`,
  `EXIT=0`.

The validator's own predicate is the oracle in the exact-incident test: the
fixture's post-CLEAN project passes `--gate core` with zero FAIL, and the
RED control drives the measured artifact (`PHASE DONE`) back through the real
writer and gets the audit-route FAIL naming `PHASE SCOUT T-1304`.

## Neighbours and gates

| check | result |
| --- | --- |
| `python -B tools/test_t1669_clean_done_projection.py` | OK (6 tests) |
| `python -B tools/test_audit_route.py` | OK (27 tests) |
| `python -B tools/test_control_primitives.py` | OK (34 tests, 1 skip) |
| `python -B tools/test_cli_compound_entry.py` | OK |
| `python -B tools/test_next_action_deadlock.py` | OK |
| `python -B tools/test_t1640_log_seal.py` | OK |
| `python -B tools/validate.py --gate core` (live home, my surface) | 54 PASS, 0 FAIL, 9 WARN, EXIT=0 (measured 00:5x) |

That live run first FAILed on `runtime manifest names a file git does not
track: tools/test_t1669_clean_done_projection.py` — the new test file was
staged (not committed) so this home's manifest gate could see it. With it
staged, the gate was green.

`live-validate-core.txt` and `live-validate-core-concurrent-future-gate.txt`
record re-runs taken AFTER the family run. Both show the SAME 4 FAILs, all
from another session's untracked document set added to the shared checkout at
01:02 (`future_gate/SAIPEN_FUTURE_GATE_TRIGGERDEV_DURABLE_RUNS_20261008/*.md`
-- "on disk but absent from the index"). Nothing in those runs names STATE,
next_action, BOARD or the audit route, and the files are not this work's; they
appeared after the green measurement above. Staging another session's files is
not mine to do, so the live gate is reported as red-on-a-foreign-surface, not
as green.

## Canonical core-unit family

`python tools/core_unit.py evidence T-1669` is the closure-boundary command:
it runs the family against a sandbox copy and then CITES the record in the
ticket's LOG, which requires a claimed T-1669. Since T-1304 owned the seat,
the family was run through the same engine entry point it uses
(`core_unit.run_family(root, jobs=6)`) with `judge` against the recorded
baseline, and WITHOUT the LOG citation or any baseline write. See
`core-unit-family.json` / `core-unit-family.log`.

Result: the declared `unit` family
(`python -B -m unittest discover -s tools -p test_*.py -v`, sharded over 6
jobs, against an immutable sandbox copy of this tree):

* `ran`: 5717 tests, `status`: PASS, wall 1451.6 s
* `red`: [] — `new_red`: [], `fixed`: []
* baseline red: [] -> `verdict`: PASS, `problems`: []

The focused regression rides inside that family run (it is imported by the
discovery), so the repair is green both narrowly and across the family.

## Known, pre-existing, out of scope

* A tripped goal safety valve with `destination == "DONE"` still commits a
  value the validator rejects: the router's hard-stop branch restates the
  PROPOSED state's `next_action`, which the transition has just replaced. The
  pre-fix writer committed `PHASE DONE` there and was equally red; the valve's
  own route budget is T-1670's subject and was not touched.
* `_plan_finish_ticket` has the same shape by construction (it is the
  semantic reference this repair copies), including that corner.

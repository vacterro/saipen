# T-1882 — disposition of all 110 reported failures

Source record: `.saipen/evidence/core-unit/9b10e579a60f9c79-20261024T100757701402Z.json`
(status FAIL, ran 7551, red 110, new_red 110, jobs 6, duration_s 1783.0)

The designation `new_red` in that record is a baseline-comparison result. It is
not proof that all 110 failures were caused by the latest optimization. This file
classifies each reported id by MEASURED cause, and states what is still not green.

## Method

Three measurements, all in this directory, in this order:

1. `rerun-red-modules-20261024.json` — the 37 reported modules re-executed one
   subprocess each with the harness's own invocation
   (`python -B -m unittest discover -s tools -p <module>.py -v`), against the
   CURRENT live tree.
2. `r1-runtime-parity.json` — the six modules whose dependency is absent from
   SOURCE re-executed with the SAME module bytes against the INSTALLED runtime's
   `tools/` tree (`76a5995cbf99aacc`), with the repository's project scaffolding
   beside it.
3. `r2-validator-control-set.log` — three candidate `COMMANDS.md` byte sets
   measured by one unmodified verifier (`tools/validate.py`), then the same three
   measured by `tools/protocol_budget.py --summary`.
4. `r3-ledger-control.log` and `r4-init-exemption-control.log` — one verifier
   each, held fixed, over a throwaway copy where only the repaired subject
   differs between the red and green halves.

## Result

| Disposition | Count | Evidence |
|---|---|---|
| NOW_PASS on the live tree | 55 | `rerun-red-modules-20261024.json` |
| PASS against the installed runtime, source lacks the API | 52 | `r1-runtime-parity.json` |
| OPEN — owned by two untracked foreign documents | 3 | `test_t1581_phase_rename_knowledge` |
| **Total** | **110** | |

## The 55 that now pass

Repaired by this ticket, or revealed green by the repair:

- **R2 — FUTURE publication surface (23 ids).** `saipen/COMMANDS.md` in the
  worktree had been replaced by bytes byte-identical to the installed runtime
  (`md5 30c33300298b218d0b430ce571cc2729`, 118 lines) which carry no
  `saipen future` rows, so the validator's `FUTURE-OWNER` check emitted four
  FAILs in every fixture that copied the protocol directory. Those four FAILs
  were then quoted verbatim in 19 further red sections. The five rows are back,
  and the document is 41546/56320 on `command_resolution` (PASS).

  The control is not the budget alone, and that matters: the pre-fix bytes PASS
  the budget (40427/56320) while FAILING `FUTURE-OWNER` with four FAILs. Simply
  restoring the stored HEAD version fixes FUTURE-OWNER but breaks the budget
  (57232/56320, over by 912). Only the compact five-row block satisfies both.
  `r2-validator-control-set.log` records all three variants on both verifiers.
- **R3 — fail-site ledger (5 ids, `test_check_inventory`).** The worktree ledger
  had drifted from the worktree validator: `ADDED fail site e736f31b20f2d116 at
  tools/validate.py:5966`. Regenerated, and the one pre-existing adjudication was
  restored by identity (message, qualname and ordinal all unchanged), never
  invented.
- **R4 — this campaign's own T-1881 gate (16 ids).** The authority gate refused
  `ticket add` under the INIT pause `WAIT: init -- provide the first project
  goal or raw backlog`, which creating that first Work IS the only documented
  answer to. Exempted by WAIT CATEGORY, not by wording.
- **Residual (11 ids).** Green in the rerun with no edit of their own; they were
  red because the same fixtures embedded the R2/R3/R4 FAIL text.

## The 52 that pass against the installed runtime

These modules exist in the index and the worktree but in NO commit, and they
call a release API the source has not received:
`TERMINAL_PUBLISHED`, `TERMINAL_LOCAL_NO_PUBLISH`, `_gate_command`,
`_writer_locked_git_bound`, `_gate_window_drift`, `_crew_terminal_route`,
`_crew_carrier_problem`, `_release_op_started`, `_scope_identity_holds`,
`_source_identity_drift`, `_staged_index_drift`, `_bounded_source_drift`,
`_ship_label`, `_no_publish_targets_untouched`, `PUBLICATION_PERFORMED`,
`PUBLICATION_NOT_PERFORMED`, `LOCKED_GIT_TIMEOUT`.

Source `tools/saipen_engine/release.py` is 4874 lines with **zero** occurrences
of those symbols; both installed runtimes are 5312 lines and byte-identical to
each other. The source is a strict SUBSET: zero source-only symbols. Executed
against the runtime's `tools/` tree the same module bytes pass 107/107 tests
with no edit:

| Module | Reported red | Runtime result |
|---|---|---|
| `test_t1746_crew_terminal_outcome` | 35 | 45/45 PASS |
| `test_t1750_release_boundary` | 11 | 11/11 PASS |
| `test_t1827_writer_lock_contract` | 1 | 19/19 PASS |
| `test_t1681_release_closure_op` | 3 | 5/5 PASS |
| `test_t1828_verification_policy` | 1 | 14/14 PASS |
| `test_source_contract_derivation` | 1 | 13/13 PASS |

This is an unreleased in-flight batch calling an API the source has not received.
Warming the source is a publication decision (T-1815 / T-1644), not a regression
repair, and this ticket does not make it.

## The 3 that remain OPEN

`test_t1581_phase_rename_knowledge`, all three failures, one cause:

```
FAIL: coverage gap -- 1 shipped document(s) are read by no check and declared
exempt by none: saipen/COMMANDS_REFERENCE.md
```

`saipen/COMMANDS_REFERENCE.md` and
`SAIHANDOFF_FASTPROMPTER_PERSONAL_AUDIO_RESTORATION.md` are untracked and absent
from HEAD and from the index. The worktree `saipen/MANIFEST.json` diff adds
`"src": "saipen/COMMANDS_REFERENCE.md"`, so a copied runtime carries the file
while the validator neither covers nor exempts it. Probes in throwaway copies:
dropping both files plus the manifest entry clears the gap; dropping only the
entry does not; dropping only the file yields `runtime manifest file missing from
the home`.

Left untouched and reported. Exempting them would adjudicate another actor's
unreleased work, and `tools/validate.py` is itself part of the staged foreign
batch.

## What this does NOT claim

- **No FULL 7,551-test re-run was made after the repairs.** Only the 37 reported
  modules were re-executed, plus the focused gate (69 tests, PASS). FAST success
  is not FULL success and is not recorded as such.
- **The live tree is not green.** The validator emits 39 FAILs: 36 "runtime
  manifest names a file git does not track" (foreign t1859–t1876 modules and this
  campaign's own three new test files, none of them committed), plus the
  EX-000022 closure-provenance staleness outside this ticket's scope, the
  root-file-set drift, and the coverage gap above.
- **No baseline file was edited.** `.saipen/evidence/core-unit/baseline.json` is
  untouched; the 110 reds are not accepted as expected.
- **Nothing was unstaged, reset, cleaned, stashed or force-pushed.**

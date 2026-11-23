# T-1892 — `Journal.read()` is one decoder, not two

CORE-001 says one strict decoder owns both `operation.json` and the
`progress.json` sidecar. `Journal.read()` was a second decoder. It re-read the
manifest itself and merged the sidecar inside a bare `except Exception: pass`,
so every shape `decode_operation_record` refuses was silently merged instead.

## The measured divergence (before the fix)

Each row is one disposable project whose sidecar carries the named shape. The
left column is `decode_operation_record`, the right column is what
`Journal.read()` returned for the same bytes on the same tree.

| sidecar shape | canonical decoder | `read()` before the fix |
| --- | --- | --- |
| invalid JSON | `RECOVERY_CONFLICT` | `status='PREPARED'` (sidecar dropped) |
| not a JSON object | `RECOVERY_CONFLICT` | merged as if absent |
| status outside the closed set | `VALIDATION_FAILED` | that status, verbatim |
| `progress_index` not an integer | `VALIDATION_FAILED` | merged unvalidated |
| `progress_index` out of range | `VALIDATION_FAILED` | `status='APPLYING'` |
| `applied_frontier` not an integer | `VALIDATION_FAILED` | merged unvalidated |
| `applied_frontier` out of range | `VALIDATION_FAILED` | `status='APPLYING'` |
| terminal sidecar over an unresolved manifest | `RECOVERY_CONFLICT` | `status='COMMITTED'` |
| a directory where the sidecar belongs | `RECOVERY_CONFLICT` | dropped |

The last two rows are the load-bearing ones. A forged terminal status was
visible through `read()`, and two readers trusted exactly that projection:

* `release._recover_release_op_locked` reads the record and then decides
  `ALREADY_APPLIED` on `status == "COMMITTED" and release_stage == "COMMITTED"`;
* `goal_authority._pin_record` compares `read()` against the record it already
  holds and raises `"continuation journal changed while being read"`.

The project-wide scan was already right, which is what made the projection a
defect rather than a tolerance. Feeding the same forged bytes to
`scan_pending` produced:

    pending:   [('op-t1892-fold', 'CORRUPT_JOURNAL', True)]
    preflight: {'ok': False, 'code': 'CORRUPT_JOURNAL', ...}
    detail:    "progress.json claims terminal 'COMMITTED' but manifest is
                'PREPARED'; settlement did not fold"

So the engine called the receipt unreadable while `read()` handed back
`COMMITTED`. There is no reading under which both are correct.

## Why the fix is not a straight delegation

The strict decoder refuses the one window the writer legitimately creates.
`Journal.mark()` publishes the terminal status to the sidecar and only then
calls `fold_progress()`, which calls `read()` inside exactly that window:

    mark("COMMITTED") -> sidecar COMMITTED over PREPARED manifest
                      -> fold_progress() -> read()
                      -> fold into manifest, unlink sidecar, settle

Delegating naively would have made every settlement raise. So the contradiction
branch is guarded by a narrowly-scoped `allow_settlement_fold` flag that
threads `Journal.read` -> `decode_operation_record` -> `_merge_progress_sidecar`
-> `_decode_progress_sidecar`, and **exactly one caller** passes it:
`fold_progress`. Every other reader keeps the contradiction as a refusal.

## The change

`tools/saipen_engine/journal.py`

* `class JournalDecodeRefusal(ValueError)` carries the decoder's `code` and
  `detail`. Subclassing `ValueError` keeps every existing caller that treats
  "this journal cannot be read" as a `ValueError` working unchanged.
* `Journal.read(*, allow_settlement_fold=False)` delegates to
  `decode_operation_record` and raises on refusal. The permissive projection is
  gone.
* `fold_progress()` passes `allow_settlement_fold=True`.
* `_decode_progress_sidecar`, `_merge_progress_sidecar` and
  `decode_operation_record` gained the keyword, defaulting to `False`.

`tools/saipen_engine/release.py` — two call sites read a journal and then acted
on its status, and neither guarded the read:

* `_apply_closure_targets` now converts a refusal into
  `ReleaseRefusal("RECOVERY_CONFLICT", ...)`;
* `_recover_release_op_locked` returns the same code as a structured refusal
  with `recovery_required: True`, instead of propagating a `ValueError` out of
  a public recovery entry point.

`tools/test_t1892_one_decoder.py` — 12 controls, one per clause of the ticket's
verify line. `tools/sandbox_scope.json` — the module declared `[]`, since it
reads only the source tree.

## Verification

**The population.** Every receipt on this checkout — active ops plus the whole
settled directory — decoded through the new `Journal.read()`:

    read=16197  refused=0  in 21.8s

No live receipt was readable before and refused after, so the new refusal does
not fire on real history.

**The control.** `.saipen/evidence/T-1892-one-decoder/red-control.py` runs the
same three assertions twice in one process: once on this tree, once with
`Journal.read` and `Journal.fold_progress` monkeypatched back to their exact
HEAD bodies. Transcript in `red-control.log`:

    current tree green            : True
    pre-fix tree green            : False
    pre-fix legitimate merge green: True
    CONTROL OK -- the refusals are the fix, not the harness.

The third line matters as much as the second: the legitimate-merge control
passes on both trees, so the red is the refusal appearing, not the harness
failing to run. On the pre-fix bodies all eight refused shapes reported `OK`
and the refusal test failed 9 assertions.

**The family.** Two runs, diffed against the recorded baseline
(`core-unit/0ade2cd4b0d85ad8-20261024T142656492584Z.json`, 55 red):

| run | modules | tests | red | new reds vs baseline |
| --- | --- | --- | --- | --- |
| journal/recovery/settlement | 10 | 215 | 46 | **0** |
| release/acceptance/lock | 8 | 180 | 4 | **0** |

All 50 reds are baseline rows in `test_t1746_crew_terminal_outcome`,
`test_t1750_release_boundary`, `test_t1681_release_closure_op` and
`test_t1828_verification_policy`. Transcripts: `family-run.log`,
`family-run-2.log`.

**The focused gate.**

    python tools/core_unit.py focused T-1892 \
      --pattern test_t1892_one_decoder.py \
      --pattern test_journal_nested_targets.py \
      --pattern test_recovery_noop_targets.py \
      --pattern test_t1316_recovery_already_applied.py

    verdict PASS  ran 67  duration_s 80.563
    record .saipen/evidence/focused-unit/ba99d300236fe9fb-20261024T202802549237Z.json

The record's `sandbox_scope` says `mode: FULL` with three undeclared pattern
modules — the correct fail-closed default for modules nobody has yet measured
in a narrowed sandbox. `test_t1892_one_decoder.py` itself is declared.

## Not claimed

* This is a **focused** gate, not the full family. The 7576-test suite was not
  rerun; the recorded baseline still stands at 55 red and nothing here claims
  otherwise.
* The 50 reds observed in the family runs are **not** re-attributed: they match
  the baseline by exact test id and the diff shows zero additions, which is all
  this ticket asserts about them.
* Publication state is `pending`. `saipen ship` still refuses on the foreign
  staged batch, which is the standing operator blocker and not this ticket's to
  clear.
* The decoder was not widened, and `allow_settlement_fold` was not given a
  second caller. If a future reader needs it, that is a new decision with its
  own evidence, not a default.

# HUNT-018: bounded six-signal sensor sweep at 66ef622a (tree 70f5cdf4)

Re-measurement of the sensor state against the current source identity:
HEAD 66ef622a43ab59512735ac78ce10d1250e26f9df, tree fingerprint
git-delta-v1:70f5cdf466bec8bfea2f78ab6ffb896a546d1ac31c61c538ba166582f289f33b
(the tree moved after HUNT-017, whose package is bound to ad029851 and is
therefore stale under PROTOCOL.md § 6 class 1).

Raw captures: kitchen/_hunt018_validate.txt, _hunt018_t1430.txt,
_hunt018_registry.txt.

## Finding 1 -- core conformance is RED on this tree (REPRODUCED)

`python -B tools/validate.py` exits 1 with `Validation FAILED: 5 problem(s), 16 warning(s)`.
The five problems, verbatim:

1. `FAIL: closure provenance does not resolve: EX-000050 was verified against installed engine generation sha256:c6819eff239d8b9c... but the running engine is sha256:6a15b7cc39a12655... -- the dependency moved (rollback or upgrade): re-resolve truthfully instead of inheriting a stale green -- a DONE line may record HOW it closed, never that something was published when it was not (CORE-003)`
2. `FAIL: runtime manifest names a file git does not track: tools/saipen_operator_gateway.py`
3. `FAIL: runtime manifest names a file git does not track: tools/test_t2040_external_terminal_proof.py`
4. `FAIL: runtime manifest names a file git does not track: tools/test_t2045_operator_gateway.py`
5. `FAIL: runtime manifest names a file git does not track: extensions/adapters/FREEBUFF_INGRESS_CONTRACT.md`

HUNT-017 recorded `Agent is conformant ... 0 problem(s)` at tree ad029851; that
claim no longer holds here, so the historical green is superseded, not inherited.

- Verdict: **REPRODUCED**. Gate evidence: exit 1, 5 FAIL lines above.

## Finding 2 -- the four untracked manifest files have no open BOARD ticket (REPRODUCED)

`BOARD.md ## TODO` holds T-2044, T-2043, T-2042, T-2041 and none of them owns
the packaging debt; the only surface naming those four paths is cohort C-021
(scope 5 files, publication_status pending) and crew stage SC-2, which is
`UNSATISFIED` with action `RUN_ROLE`. So the four FAIL lines are not yet
tracked as Core work anywhere and no committed path reaches git.

- Verdict: **REPRODUCED**. Evidence: the four FAIL lines above plus the current
  BOARD/cohort read; `git status --porcelain` reports 3645 changed paths.

## Finding 3 -- crew_run receipt writer reachability holds (NOT_REPRODUCED)

`operations.record_crew_run` is defined at
`tools/saipen_engine/operations.py:26480` and called from
`tools/saipen_engine/crew.py:1546`; `python -B tools/test_t1430_crew_run_receipt.py`
prints `OK` and exits 0. The orphan-writer defect HUNT-015/016 reported for
`record_producer_integration` is retired: a whole-tree grep for that name now
yields zero matches.

- Verdict: **NOT_REPRODUCED** as defect.

## Finding 4 -- refusal-registry completeness is green (NOT_REPRODUCED)

`python -B tools/test_refusal_registry.py` prints `OK` and exits 0 on this tree.
The single code SRC-400 needed (`EXTERNAL_TERMINAL_EVIDENCE_INVALID`) is
registered in `saipen/REGISTRY.json` and produced by
`tools/saipen_engine/external.py:578`. A naive `"code":` census over
tools/saipen_engine shows 424 literals of which 210 are outside the registry,
but those are success/status codes (`COMMITTED`, `CHECKPOINTED`, `FINISHED`,
`DRY_RUN`, ...), not refusal codes, and the registry gate that owns the refusal
set passes -- recorded here so nobody mistakes the census for a defect.

- Verdict: **NOT_REPRODUCED** as defect.

## Finding 5 -- a stale TODO names a closed ticket (REPRODUCED)

52 `TODO`/`FIXME`/`HACK` markers in tools/ and saipen/ name a `T-####` ticket;
exactly one of them names a ticket BOARD shows `[x] DONE`:
`tools/test_release_reconciliation.py:430` -- `TODO ... T-2000`.

- Verdict: **REPRODUCED**. Minimal evidence: the line above plus the DONE row
  for T-2000 on `.saipen/BOARD.md`.

## Finding 6 -- 29 zero-reference top-level defs in the shipped tooling (REPRODUCED)

Whole-tree identifier census over tools/, saipen/ and extensions/ (identifiers
counted inside string literals too, so `getattr(m, "name")` counts as a
reference): 29 top-level `def` names whose total occurrence count is 1, i.e.
their own definition line and nothing else. First entries:

- `bump_int_line` -- tools/audit_checks.py:1377
- `release_claimed_work` -- tools/audit_checks.py:1924
- `baseline_ids` -- tools/fail_site_inventory.py:311
- `seat_key` -- tools/improve.py:260
- `report_fingerprint` -- tools/improve.py:455
- `producer_gate_is_hard` -- tools/validate.py:5286
- `is_applicable` -- tools/saipen_engine/applicability.py:238
- `admission_error` -- tools/saipen_engine/attempt.py:453
- `detached_ticket_id_errors` -- tools/saipen_engine/board.py:577
- `resumable_parent` -- tools/saipen_engine/board.py:1566
- `write_document` -- tools/saipen_engine/codec.py:289
- `encode_preserving` -- tools/saipen_engine/codec.py:305
- `is_declared_shortcut` -- tools/saipen_engine/commands.py:162
- `stale_cycles` -- tools/saipen_engine/continue_fallback.py:217
- `register_provider` -- tools/saipen_engine/discovery_providers.py:1330

None of these is on BOARD as an open ticket.

- Verdict: **REPRODUCED**. Minimal evidence: the census printout above; a
  zero-reference `def` is dead code or an unused helper, never reachable
  behaviour.

# HUNT-019: bounded six-signal sensor sweep at 66ef622a (tree e4fe1f84)

Current identity: `66ef622a43ab59512735ac78ce10d1250e26f9df` /
`git-delta-v1:e4fe1f84c67c2ebd8af3e8d7461569cfd826aaa140e1f7d364d5505e29dfc07f`.
Raw captures: `_hunt019_validate.txt`, `_hunt019_registry.txt`,
`_hunt019_t1430.txt`, `_hunt019_unverified.txt`, `_hunt019_todo.txt`,
`_hunt019_silent.txt`, `_hunt019_census.txt`, `_hunt019_board_signals.txt`.

## Signal 1 — failing tests/gates: REPRODUCED

`python -B tools/validate.py` exits 1: 23 problems, 33 warnings. Exact FAIL
lines are in `_hunt019_validate.txt`: unresolved SRC-167/SRC-407/SRC-410;
stale EX-000050 and absent cohort C-021; FG-0046 names absent T-1936; 17
runtime-manifest files are outside Git; 32 locale README badges drift. These
classes already belong to active Core T-1449, so this run adds evidence, not a
new finding. Instrument controls: refusal registry 6/6 PASS; crew-run receipt
3/3 PASS. Verdict: **REPRODUCED**.

## Signal 2 — commits unverified in LOG: BLOCKED

A literal recent-commit census finds 11 of 25 full/short hashes absent from the
active and archived LOG text. Literal absence alone cannot distinguish an
unverified commit from publication evidence keyed by ticket/event/other
commit; no canonical verifier declaring these commits unverified was found.
Verdict: **BLOCKED** pending semantic release-ledger attribution; no defect is
claimed.

## Signal 3 — stale TODO/FIXME/HACK: BLOCKED

The broad text census yields 1530 lines, including fixtures, quoted protocol
text, generated evidence and intentional controls. This over-approximates the
signal and cannot establish staleness without per-marker ownership/history.
The prior HUNT-018 candidate `tools/test_release_reconciliation.py:430` is no
longer present, so it is not inherited. Verdict: **BLOCKED** pending bounded
per-marker ownership review; no new defect claimed.

## Signal 4 — silent failures: BLOCKED

AST finds 64 empty/pass exception handlers. The count includes deliberate
best-effort cleanup and tests; AST shape alone does not prove ignored required
I/O. Exact locations are in `_hunt019_silent.txt`. Verdict: **BLOCKED** pending
per-handler failure-path reproduction; no new defect claimed.

## Signal 5 — symmetry gaps: NOT_REPRODUCED

Search of current BOARD ownership and relevant save/load, undo/redo,
import/export, start/stop vocabulary produced no bounded unowned asymmetry
that could be reproduced in this pass. Verdict: **NOT_REPRODUCED**.

## Signal 6 — dead code/orphan files: BLOCKED

The available census reports 421 nominal zero-reference definitions across
760 definitions, but it counts fixtures, callbacks, dynamic imports, generated
evidence and nested definitions. Identifier count is not reachability proof.
Canonical validator independently reproduces 17 manifest files absent from
Git; T-1449 already owns that publication defect. Verdict: **BLOCKED** for any
new dead-code claim; no new ticket proposed.

This is a fresh saihunt run at the current source epoch. No file outside the
saihunt namespace was written by the role.

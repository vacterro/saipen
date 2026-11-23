# HUNT-020: bounded six-signal sweep at dc39709c (tree 6a857897)

Current identity: `dc39709c0c17a3272126c01a626ffcaa4176140b` /
`git-delta-v1:6a857897f61278f309f56252e9d382c1f3221c91920708dc17e2d65ee16566bd`.
Role revision: `sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5`.
Raw captures: `_hunt020_validate.txt`, `_hunt020_controls.txt`, `_hunt020_gc.txt`,
`_hunt020_static.txt`, `_hunt020_todo.txt`, `_hunt020_git_status.txt`.

This pass is bounded to the current validator output, current Python/tool
censuses, and the recently changed T-2059 GC/closure surfaces. It does not
claim a full repository audit or convert static counts into defects.

## Signal 1 -- failing tests/gates: REPRODUCED

`python -B tools/validate.py` exits 1 with 29 problems and 36 warnings. The 29
problems are: unresolved SRC-167/T-1606; stale closure provenance EX-000052;
the audit inbox route not followed; FG-0046 naming absent T-1936; and 25
runtime-manifest paths not tracked by Git. The focused refusal-registry and
crew-run controls pass 9/9. `python -B -m unittest tools.test_gc` passes 63
tests with 1 skipped. Exact validator lines are in `_hunt020_validate.txt`;
test output is in `_hunt020_controls.txt` and `_hunt020_gc.txt`. Existing
ownership is recorded in the current Core BOARD (T-1606 and T-1449); no new
finding is proposed. Verdict: **REPRODUCED**.

## Signal 2 -- commits unverified in LOG: BLOCKED

A literal census compared the last 25 Git commit hashes with the active and
archived Core LOG text; all 25 hashes were absent. Literal absence cannot
distinguish an unverified commit from release or ticket evidence recorded by
another identity, so this does not establish a defect. The result is in
`_hunt020_static.txt`. Verdict: **BLOCKED** pending semantic release-ledger
attribution; no commit is claimed unverified.

## Signal 3 -- stale TODO/FIXME/HACK: BLOCKED

The bounded Python census found 974 word-boundary candidate lines under
`tools/`. It includes protocol vocabulary, tests and section names. No
per-marker age/ownership review was done, so the count cannot establish
staleness. The T-2059 source surfaces contain only intentional TODO section
names/comments in the existing operations and release code, not a reproduced
stale marker. Verdict: **BLOCKED** pending individual ownership/history review;
no new defect claimed.

## Signal 4 -- silent failures: BLOCKED

An AST census found 63 `except` handlers whose sole body is `pass` across the
Python tools. This includes tests and deliberate best-effort cleanup. The
T-2059 closure hook at `tools/saipen_engine/operations.py:5325-5337` records a
durable maintenance failure and only swallows a second failure while trying
to record that post-commit failure. Static shape alone does not show a lost
required outcome; no failure-path reproduction was run. Verdict: **BLOCKED**
pending per-handler failure-path review; no new defect claimed.

## Signal 5 -- symmetry gaps: NOT_REPRODUCED

On the bounded T-2059 persistence surface, `gc.load_state` pairs with
`gc.save_state`, the committed-closure counter feeds the maintenance settle
path, and the GC module is reached from the completion hook. The 63-test GC
suite passed (1 skipped). This pass reproduced no persistence/read-write
asymmetry in those surfaces. This verdict does not clear the separately
tracked concurrent-checkpoint issue T-2062. Verdict: **NOT_REPRODUCED**.

## Signal 6 -- dead code/orphan files: BLOCKED

The Python AST census found 19,412 function/class definitions and 12,478 names
with no lexical `Name(Load)` reference. Attribute calls, callbacks, dynamic
imports, tests and entry points make this an intentionally over-broad
candidate list, not a reachability proof. In the changed T-2059 area, `gc.py`
is imported by the production closure hook and exercised by `test_gc.py`;
no orphan was reproduced there. The 25 untracked runtime-manifest paths are
already a publication/conformance issue, not evidence of dead code. Verdict:
**BLOCKED** for any new dead-code claim; no new defect claimed.

The role wrote only within `.saipen/extensions/subs/saihunt/`. No payload is
proposed. Core can record the current package for its crew epoch with the
canonical `saipen crew record-run saihunt` route.

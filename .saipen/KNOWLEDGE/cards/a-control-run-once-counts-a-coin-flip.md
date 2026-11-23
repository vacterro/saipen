<!-- SAIPEN KNOWLEDGE CARD v1 -->
kind: trap
scope: tests over receipts, journal records and other engine-ordered lists, mutation controls, a test that passes alone and is red in the declared family
trigger: asserting an index into a list the engine sorted, running a mutation control, or reading "undetected 0" off a control script
status: active
evidence: T-1304, .saipen/evidence/core-unit/7f032a94ff531e9e-20261007T200438Z.json, .saipen/evidence/T-1304-layer16/mutate1304.out.txt, .saipen/evidence/T-1304-layer16/mutate1304.py, .saipen/evidence/T-1304-layer16/repeat_runs.py, tools/test_t1304_r009_settled_wiring.py
supersedes: none

# A control run once counts a coin flip as a detection

Repeat a new test and every mutation control, and compare the set of red test names between repetitions, because a test whose outcome follows a random name passes a focused run half the time and reads as "detected" under any mutation at all.

Why:
T-1304's test compared position `[0]` of an operation query before and after a second settlement. Receipts are ordered by `(created_at, op_id)`: `created_at` has one-second resolution and the op id is a random name, so two operations made inside one second come back in either order. Twelve isolated runs: six green. The focused run, 855 neighbouring tests and the mutation control all passed by luck, and twenty minutes of the declared family were spent finding it. The control's own output already showed it: the test was red under three mutations that cannot reach it. Only the last line, "undetected 0", was read.

How to apply:
For anything the engine orders by an op id or a second-resolution stamp, assert membership, or equality with the canonical answer, never a position. A mutation script runs the unmutated control and each mutation three times and fails when a test is red in some repetitions only. Read each mutation's red names against the one property it removes; a name the mutation cannot reach is a finding about the test, not a detection.

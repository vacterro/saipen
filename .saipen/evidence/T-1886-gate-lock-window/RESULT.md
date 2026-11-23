# T-1886 RESULT — the ship gate now runs with the writer mutex released

## The defect

`tools/saipen_engine/lock.py:812` already defines `writer_lock_yielded`. Its
own docstring names the ticket that asked for it (T-1827 / SRC-282:R003) and
states the reason plainly: a validator subprocess "can run for minutes, and
holding the only writer mutex across it makes every other mutation refuse
WRITER_BUSY for that whole span."

The helper landed. **Its call site never did.** A repo-wide search for
non-test callers returned zero:

```
tools/saipen_engine/lock.py:812:def writer_lock_yielded(...)   <- definition
tools/test_t1827_writer_lock_contract.py:381:  with lock_mod.writer_lock_yielded(lock):
```

So the real path was still `_apply_release` -> `_apply_release_locked` ->
`_stage_and_commit` -> `_run_gate`. Measured on this tree:

```
python tools/validate.py --gate ship   ->  19.3s, exit 1
```

For 19.3 seconds of every release, the project's single writer mutex was held
while a read-only subprocess ran, and every other mutation — a `saipen`
checkpoint, another agent's ticket transition — was refused `WRITER_BUSY`.

## The change

The held lock is now threaded to the two call sites that spawn a validator,
and both yield it for the window:

| function | before | after |
|---|---|---|
| `_apply_release` | `with project_writer_lock(root):` | `as lock` -> `_apply_release_locked(root, plan, lock=lock)` |
| `_stage_and_commit` | `_run_gate(root, "ship")` | `with writer_lock_yielded(lock): _run_gate(...)` |
| `_apply_no_publish` | `with project_writer_lock(root):` | `as lock` -> `_apply_no_publish_locked(..., lock=lock)` |
| `_no_publish_body` | `_run_gate(root, "core")` | `with writer_lock_yielded(lock): _run_gate(...)` |

Both paths are covered because both run a validator: the full publish path runs
`--gate ship`, the no-publish path runs `--gate core`. Fixing only the first
was measurably insufficient — the probe took the no-publish route and still
reported the lock held.

A lost re-acquisition is fail-closed. `writer_lock_yielded` re-takes the mutex
on exit and raises `WriterBusy` when another writer won the window; the release
then returns `SHIP_GATE` (full path) or `WRITER_BUSY` (no-publish path, where
the existing outer handler answers) and **nothing is committed**. Both labels
mean the same thing, so the test asserts the substance — `ok` is false and the
code is not `RELEASED` — rather than one layer's spelling.

## Proof — one fixture, two byte sets

The control swaps only `release.py` for its `HEAD` bytes and runs the identical
fixture, so the difference cannot be anything else:

```
RED   pre-fix bytes (HEAD): exec_ok=True gate_ran=True held_during_gate=True  lock_after=free
GREEN post-fix bytes:       exec_ok=True gate_ran=True held_during_gate=False lock_after=free
```

`held_during_gate` is read from inside the gate callback, i.e. the real lock
state at the moment the subprocess would spawn — not an inference from the
source.

Module: `tools/test_t1886_gate_lock_window.py`, 3 tests, `OK`.

| test | what it pins |
|---|---|
| `test_the_gate_runs_with_the_writer_mutex_released` | gate sees `held=False`, lock free afterwards |
| `test_a_writer_that_wins_the_window_refuses_the_release` | a concurrent thief makes the release stop without committing |
| `test_the_production_path_calls_writer_lock_yielded` | a spy on the real helper, so deleting the integration fails |

The third test exists because the first two could pass for the wrong reason
(a future refactor might leave the lock free by accident); it fails if
`writer_lock_yielded` is not actually called.

## Focused gate

```
python tools/core_unit.py focused T-1886 --pattern test_t1886_gate_lock_window.py
{"verdict": "PASS", "ran": 3, "reused": false,
 "record": ".saipen/evidence/focused-unit/3da061c60895afed-20261024T174635441153Z.json"}
sha256 069ec1f132ecf74413e88f687fb64498d5818059b362be5797c5a37864399dd3
```

## Why the selection is narrow — and why that is honest

An earlier gate selection included `test_t1746_crew_terminal_outcome.py`, whose
fixture this module borrows. That run reported `FAIL` with 45 tests, so it was
checked against the baseline before being trusted: **35 of its 45 tests are
already in the 55-red baseline** (`test_t1746` appears in `red` of
`0ade2cd4b0d85ad8-20261024T142656492584Z.json`). Including a module that was
red before this change and is red after it would have added no evidence about
this fix and would have made a red baseline look like my regression.

The borrowed fixture is covered instead by the fact that this module's own
tests exercise the real `plan_release` / `execute_release` path end to end on a
fixture that reaches the gate — the same path, without claiming the other
module's 35 inherited reds.

## Adjacent defect found, not fixed here

`tools/test_t1827_writer_lock_contract.py:429` asserts this same R003
invariant, but calls `fixture._shape()` with no arguments. `_shape` writes a
VERSION only when given one, and `plan_release` now requires it, so that test
dies inside `plan_release` before the gate runs:

```
ReleaseRefusal: REFUSE [VALIDATION_FAILED] VERSION is missing from the repository root
```

That file is **staged and not in HEAD** — another actor's in-flight work — so
it is not mine to edit, and INV-09 forbids overwriting concurrent modifications.
Recorded here so whoever owns it sees the exact diagnosis: pass
`version="8.0.1", ticket="T-11", wide=False` and the invariant becomes
measurable (verified: with that call the test passes against this fix).

What is NOT claimed: the full family is green (it is not; the 55 baseline reds
are untouched), deployment happened (it did not; 437 foreign injected-surface
paths still block the installer), and the 19.3s gate itself got faster (it did
not — the change removes a lock hold, not the gate).

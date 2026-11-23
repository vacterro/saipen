# T-1953 VERIFY — what was run, and what it said

## Focused record

```
python tools/core_unit.py focused T-1953 --pattern test_t1953_suite_reuse.py --agent saipen-cli
```

```
verdict: PASS   ran: 11
record: .saipen/evidence/focused-unit/718e780893093386-20261029T070920721875Z.json
duration_s: 104.813   checkpoint: CHECKPOINTED
```

## RED control

With the reuse branch disabled in place (`if False:` before
`reusable_record`), the same module:

```
FAILED (failures=2, errors=2)
```

Restored:

```
Ran 11 tests in 2.308s
OK
```

Two failures and two errors without the repair is the proof that the tests test
the repair and not themselves.

## Direct regression set

| module | result |
|---|---|
| `test_t1953_suite_reuse` | Ran 11 / OK |
| `test_t1658_suite_record` | (in 44) OK |
| `test_t1661_suite_projection` | (in 44) OK |
| `test_t1891_freshness_parser` | Ran 12 / OK |
| `test_t1511_soak_source_identity` | Ran 7 / OK |
| `test_t1687_identity_diagnostics` | OK |
| `test_install_identity_doctor` | OK |
| `test_t1734_source_drift` | OK |
| `test_engine_module_identity` | OK |
| `test_t1952_sandbox_points_at_itself` | Ran 6 / OK |

`ruff check` on `tools/test_t1953_suite_reuse.py`,
`tools/saipen_engine/suite_record.py`, `tools/freshness.py`:
**All checks passed!**

## Live behaviour, not just unit tests

Reuse and execution are distinguishable in the real LOG of the fixture:

```
RUN: SUITE-EVIDENCE PASS         record:...T070533579111Z.json sha256:845fa86c77878da7...
RUN: SUITE-EVIDENCE PASS-REUSED  record:...T070533579111Z.json sha256:845fa86c77878da7...
```

Same record, same sha256: the reuse line points at the execution that earned it
rather than restating a verdict.

A `PASS-REUSED` cycle still reaches SHIP:

```
saipen transition SHIP T-1 "reuse evidence accepted"  ->  TRANSITIONED
```

which is the check that matters most — the repair must not create evidence the
gates reject, nor evidence they accept for the wrong reason.

## Path canonicality, measured directly

```
plain file         -> OK  ...\a.py
nested dir slash   -> OK  ...\nested
deep dir slash     -> OK  ...\nested\sub
dotdot             -> FreshnessError: non-canonical path: b'../x'
dot                -> FreshnessError: non-canonical path: b'./x'
absolute           -> FreshnessError: invalid path: b'/x'
empty              -> FreshnessError: invalid path: b''
```

Acceptance widened by exactly one spelling git itself emits; every bound that
stops a path escaping the root is unchanged.

## Consumer-project safety

`_BZDECOMP` was read (5737 settled receipts, 273 suite records) and never
written. Its `claim`/`transition` were exercised only as `--dry-run`. Its suite
was never executed by this work; its durations are read from its own records.

## Honest regressions

1. `status` in `_BZDECOMP`: **4.4 s -> 9.35 s**. The identity now succeeds
   where it used to fail, and computing it costs 5.9 s
   (5 237 untracked files × 3 reads). Correctness purchase, reported not hidden.
2. `compute_source_identity` call count inside one `status`: **4 -> 1**. That is
   the direction PERF-001 always intended, and it only became observable once
   the exception stopped defeating it.

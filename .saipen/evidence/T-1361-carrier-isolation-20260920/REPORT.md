# T-1361 — session-carrier fixture leak: shared-cause repair and remeasurement

Date: 2026-09-20. Session astra. HEAD 46400306 plus the inherited dirty tree.
Parent capture: `V:\_TEMP_\t1361-ec53042a\stdout.txt` (ec53042a, rc=1, 640 s;
sha256 6776E198...). No push, tag, release or neighbor patch in this work.

## Root cause (one shared cause, measured)

A host session's project carrier (`SAIPEN_PROJECT_ROOT`, `SAIPEN_PROJECT_LINEAGE`,
and the witness pair `SAIPEN_AGENT` / `SAIPEN_HOST_SESSION`) is inherited by every
child process the scenario suite spawns. `tools/saipen_engine/paths.py:626` then
reads the ambient lineage as the expected one and `paths.py:648-655` refuses an
explicit foreign root with `PROJECT_LINEAGE_MISMATCH`. Fixture projects have no
IDENTITY.md of their own, so they fail "as declared, but for the wrong reason"
or "declared pass, got fail". The engine behaviour is intentional (a bound
session must not mutate another project); the harness was not hermetic. Same
measurement already recorded on 2026-09-17 in
`.saipen/evidence/T-1391-T-1390-fixture-contamination-20260917/REPAIR-PATH.md`
(lines 18-24: clearing the two variables turns the same tests green).

Capture counters: 115 `FAILED:` lines; 41 `PROJECT_LINEAGE_MISMATCH`; 20
"wrong reason"; 16 "declared 'pass', got 'fail'"; 37 "missing '"; 6 harness
crashes; 3 "expected FAIL for"; 4 "exited 1".

## Fix (bounded)

`tools/run_scenarios.py`: new `session_carrier_isolation()` context and
`_SESSION_CARRIER_VARS`; `main()` wraps `_main_impl()` with it, so every
in-process probe and every child the suite spawns runs with the carriers
removed and restored afterwards. `ruff check tools/run_scenarios.py` clean.

## Anchored RED/GREEN pair (same fixture, same verifier, only isolation differs)

Fixture `tests/scenarios/active-task-not-claimed` copied to temp; run through
`run_scenario_fixture_probes()`:

```text
RED_WITH_CARRIERS: failures=1 checked=1
  active-task-not-claimed: failed as declared, but for the wrong reason --
  expected 'is not the claimed ## DOING ticket',
  first FAIL was "FAIL [PROJECT_LINEAGE_MISMATCH]: explicit project lineage
  None does not match expected 'lineage-b512942bac884a...'"
GREEN_ISOLATED: failures=0 checked=1
  PASS: active-task-not-claimed -- failed on 'is not the claimed ## DOING
  ticket', as declared
```

## Family remeasurements on current bytes (with the fix)

```text
scenario fixtures (all):            failures=0  checked=38  skipped=34
source receipts:                    63/63  checks passed
improve:                            192/192 checks passed
nitro-integrity:                    191/191 checks passed
saicrew (selector, with scrub):     rc=0
saicrew (selector, no scrub):       rc=0
release executor:                   105/140 checks passed, 35 failed
    first signature: code=RELEASE_FAILED detail=active source receipt blocks
    ship ... STALE_SCOPE: 'release scope tree identity for T-9000 differs from
    the live tree'
```

A full-suite attempt with the fix exceeded the 900-second tool budget: output
flushed 32 KB and ended in the saicrew section (block-buffered stdout, so the
last flushed line is not the stop point); the two bounded saicrew controls above
then completed rc=0 with and without the scrub, so this is a duration/budget
observation, not a hang. Fixture probes are slower now because each fixture
actually validates instead of failing fast.

## Residual clusters (post-fix, to classify next)

- release executor: 35/140 red, STALE_SCOPE tree-identity signature (owner:
  release-executor family; candidate ticket to be minted or reused).
- unmeasured after fix (were red in the capture, expected mostly R1): third
  wave 24, perf wave 2, release freshness 4, ccc 8, hunt marks 5, converge 2,
  scheduler 1, continuity probes/H28/H30, root probes, last-event probes,
  `status`/`next` CORRUPT_JOURNAL expectations.
- Prior owner set: T-1346 (stale fixtures), T-1344 (declared family closure),
  T-1345 (fail-site inventory).

## Exact next action

Rerun the remaining `*_PROBES_ONLY` families and the full suite with an
explicit longer timeout on these bytes; assign each residual to a shared cause
or its existing owner; keep T-1428's section 5A gate in force until T-1361 is
terminal or partitioned by root cause.

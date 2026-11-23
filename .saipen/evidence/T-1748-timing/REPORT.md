# T-1748 — QualityOverTimeTests Wall-Clock vs Worker Contention

## Cause
`tools/test_t1446_supervise.py` (`QualityOverTimeTests.test_the_host_bound_ends_a_progressing_slice_without_failure`) drove `supervise()` with `max_ticks=50`, `max_seconds=3.0`, and `clock=clock` where `clock()` incremented a counter by `+0.7` on every call. `supervise()` calls `clock()` multiple times per tick (`started = clock()` plus two `clock() - started` checks around child subprocess execution and post-tick reconciliation). Under 6-worker parallel execution (`tools/core_unit.py --jobs 6`), three `python` child spawns could consume >1.2s of wall time or advance the mock clock past `3.0` before the child committed 3 ticks (`last_event >= 3`). In addition, `AGENT.bump()` wrote `BOARD.md` and `STATE.md` via plain `write_text()`, which on Windows under heavy I/O load could transiently interact with parent atomic reads.

## Fix
1. `AGENT.bump()` in `tools/test_t1446_supervise.py` now writes `BOARD.md` and `STATE.md` via `saipen_engine.paths.safe_atomic_write_bytes`, matching engine atomic write semantics, with `TOOLS` prepended to `sys.path` in `SuperviseFixture.setUp`.
2. `test_the_host_bound_ends_a_progressing_slice_without_failure` now advances the logical `clock` (`0.6 * seen["events"]`) from observed child progress (`last_event` in `.saipen/STATE.md`) rather than raw `clock()` poll count, ensuring the host bound (`max_seconds=3.0`) triggers deterministically on the 5th progressing tick regardless of worker CPU/process-spawn contention.

## Verification
- Oracle: `tools/test_t1748_worker_clock.py` (5 tests: AST contract, before-copy fail control under synthetic spawn delay, current-copy pass under synthetic spawn delay, and live subprocess execution).
- Executed regression pair: `E-16057` (`REGRESSION-EVIDENCE FAIL`) / `E-16058` (`REGRESSION-EVIDENCE PASS`) via `.saipen/evidence/T-1748-timing/regression.json`.
- Target suite: `python -B -m unittest discover -s tools -p test_t1446_supervise.py -v` -> 30 tests, OK.
- Declared family: `python tools/core_unit.py evidence T-1748 --jobs 6 --timeout 5400` -> `E-16059` (`CORE-UNIT-EVIDENCE PASS`, 6706 ran, 0 red, fingerprint `76b961b27efb5112`).


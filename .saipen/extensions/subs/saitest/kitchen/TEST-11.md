# TEST-11 — continuation diagnostics and concurrency detector

Source: b7f5b51280b8f49c5fedbf7a00aeb6d4f45743ba
Tree: git-delta-v1:4c6fd9b3f13a1d7a0b203e00a759dae5eac1474eabb77cb3e39dad9da1953eb9
Date: 2026-09-20

Bound: four scenarios; no load test, network request, or product mutation.
Diagnostic scenarios ran read-only against the bound project. Unit tests use
the existing harness and its disposable fixtures.

1. Order/repetition: run `python tools/saipen.py improve --session
   glm-5-3-max-01 --dry-run --json` twice. Both return
   IMPROVE_AUDIT_ASSIGNMENT for the same seat, report_created=false.
   NOT_REPRODUCED: no duplicate admission or canonical byte change.
2. Order/repetition: run `python tools/saipen.py crew --dry-run --json` twice.
   Both select SC-3, role saitest, action RUN_ROLE. Source and checkpoint
   projections are identical; STATE/BOARD/LOG hashes are unchanged.
   NOT_REPRODUCED: read-only planning does not advance a stage or mutate it.
3. Input boundary: `python tools/saipen.py goal --help` exits 0 and prints
   usage. STATE/BOARD/LOG and active Improve roster/report hashes are unchanged
   across scenarios 1-3. NOT_REPRODUCED: help is not captured as new Work.
4. Timing-classification boundary: `python -m unittest
   tools.test_concurrency_independence` runs 9 tests in 0.893s, one failure and
   one explicitly skipped opt-in soak test. The detector reports exactly
   test_opencode_bound_launch_smoke.py:144, value 5.0. That expression is
   `self.thread.join(timeout=5)` in server cleanup, not a subprocess timeout.
   REPRODUCED; already tracked as T-1347. The other executed checks pass.

Handoff to saipython: repair only the detector's callee classification in a
private pen, retain its subprocess-timeout red control, and add a thread-join
negative control. No shared-source change is authorized by this report.

Measurement correction: an initial diagnostic projection looked for fields
under a nonexistent `plan` wrapper on CREW_PLAN. Null comparisons were
discarded; scenario 2 above was rerun against the actual top-level fields.

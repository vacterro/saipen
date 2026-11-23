# T-1432 / SRC-086 — useful continuation and roadmap refresh

Date: 2026-09-20. Source HEAD: ec53042a9262bc5bd22f2d39f2d08bef103cca3e.
The working tree contains inherited changes; this is not a release or a claim
that the entire SRC-085 mission is complete.

## Delivered in this continuation

- Canonical adoption at E-7664 preserved the same T-1432 and BUILD phase after
  the operator confirmed the previous agent had stopped and its lease expired.
  The earlier WAIT_FOREIGN_OWNER was respected; no session identifier or claim
  timestamp was copied/rewritten to bypass it.
- Linked the exact new request SRC-086 to T-1432 through source capture's
  deduplication/link operation; no duplicate implementation ticket was created.
- Fixed CLI explain-next to consume router.gate_route, the same conformance and
  closure gate chain used by status/next/continue. It now carries the canonical
  remediation command instead of directing an agent to a refused continuation.
- Added two focused CLI regressions for current-failure agreement and healthy
  continuation. Updated the gate's consumer documentation.
- Replaced the obsolete roadmap with the current source/ticket order, an
  executable small-model work-card template, bounded acceptance criteria, and
  measurements covering both human intervention and agent effort. DONE work is
  not prescribed again. Model handoff, deferred human gates and publication
  limits are explicit. No actual less-capable-model acceptance is claimed.

## Regression evidence

The SAME command was run before and after the explain-next implementation fix:

```text
python -m unittest tools.test_src085_conformance_disposition.StatusSurfaceTests.test_explain_next_agrees_with_status_and_next_on_a_red_gate tools.test_src085_conformance_disposition.StatusSurfaceTests.test_explain_next_keeps_a_healthy_route_executable
```

- Before: 2 tests, 1 failure. The ordinary failed-gate fixture selected
  `saipen continue` instead of `saipen validate` (explain-red.txt).
- After: 2 tests, PASS, with the test/fixture/expected result unchanged
  (explain-green.txt).
- Both SRC-085 focused modules: 15 tests, PASS (src085-focused.txt).
- Flat discovery of test_src085_conformance_disposition.py: 11 tests, PASS
  (src085-discovery.txt). Dotted-module green was not substituted for this.
- Related router closure readiness, conformance projection and lineage:
  44 tests, PASS, 231.367 seconds, observed tool result.
- Earlier guard/admission/hostile-matrix/automation/T-1412 combined invocation:
  152 tests passed; an additional nonexistent test_t1403_closure_readiness name
  caused one loader error. That command was NOT green. Its intended closure
  family was subsequently run under the correct name in the 44-test run.
- Ruff 0.16.0, canonical `python -m ruff check tools/ tests/`: PASS.
- Whole-worktree `git diff --check`: PASS. All nine roadmap
  relative links resolve from the roadmap's repository directory.

## Live read-only observations

The source CLI's status, permissions and explain-next all exited 0 for
AUDAPACK and PROBLIP, both in phase DONE. Their current conformance status was
STALE_FAIL, not CURRENT_FAIL; these observations do not replace the current-red
fixture proof. They did not require any neighboring project's source patch.

admission-observations.json records source-runtime event evaluation for SAIPEN,
AUDAPACK and PROBLIP. Five ordinary diagnostic/version command shapes were
admitted in each. A proposed file write was refused with NO_ACTIVE_WORK in both
DONE projects. SAIPEN had active owned Work and correctly admitted that proposal;
it was not represented as an idle project. No proposed command/write was
executed by this observation script. STATE/BOARD/LOG hashes before/after each
project's guard evaluations matched. This is guard decision evidence over live
state, not proof that an installed host hook intercepted an actual tool call.

## Wider verification remains non-green

`python tools/validate.py` exited 1: 6 problems, 29 warnings (validate.txt).
The source identity recorded there is
git-delta-v1:fb6c1525bb91fc7d9d023e0aba5546343a832c60cd40c7e3e5f1d0fc057f46b3.

The six failures are one stale/invalid Improve report group plus five runtime
files absent from Git's tracked set:

- tools/saipen_engine/host_bootstrap.py
- tools/test_host_bootstrap.py
- tools/test_instruction_loader_contracts.py
- tools/test_src085_conformance_disposition.py
- tools/test_src085_improve_run_body.py

All five files already existed untracked when this continuation started. The
conformance-disposition test also contains this continuation's new regressions.
Nothing was staged merely to change the validator's answer. These are known
integration/evidence blockers; the focused PASS does not discharge them.

Full core-unit discovery (`python -m unittest discover -s tools -p test_*.py`)
started at 18:23:19 UTC and had not finished when the declared unit-family
600-second budget elapsed. It was interrupted around 18:33:33 UTC; the process
and its direct children were then absent. Result: TIMEOUT / INCOMPLETE, not a
completed family FAIL or PASS. Partial output is core-unit-incomplete.txt; it
contains no terminal test count and must not be counted as closure evidence.
The 600-second family budget is declared by saipen_engine/test_runner.py.
For a fresh attempt preserve verbose per-test IDs and enforce that timeout.
An earlier preliminary discovery was explicitly interrupted before source edits
to avoid presenting a run spanning changed implementations as final evidence.
Neither an interrupted run nor partial progress dots establish a family verdict.

Source-runtime `runtime --check-freshness --json` returned
CANONICAL_RUNTIME_SOURCE_UNPROVEN because the source root has no installer
provenance marker. The earlier status distribution projection reported six
stale installs and DIRTY_SOURCE. No install refresh, commit, push, tag or release
was performed, and source/install parity is not claimed.

## Exact continuation

Use `python tools/saipen.py continue --json` from the repository root and load
its returned current phase. T-1432 remains open: finish/reconcile the wider
verification, resolve existing Improve lifecycle evidence through its canonical
owner, review attribution/integration of the untracked runtime files, and prove
the authorized installed entry path. Do not repeatedly validate unchanged red
evidence or close SRC-085 from the focused tests. Then follow the reserved
T-1361 / SRC-083 / SRC-084 corridor in the refreshed roadmap.

The code graph excludes tools/ at generation 2026-09-01T13:16:39Z; this report's
implementation statements use direct current-source reads and test evidence.

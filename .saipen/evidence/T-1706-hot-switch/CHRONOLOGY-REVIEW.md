# T-1707 — a new failure invalidates the earlier regression PASS

The current-cycle regression selector used the latest FAIL and latest PASS
independently, without checking their authoritative sequence. Consequently
`PASS, FAIL` and `FAIL, PASS, FAIL` were classified as admissible. Actual
canonical operations then transitioned VERIFY to REVIEW and finished a SHIP
ticket after its newer failure. An ordinary verification PASS did not repair
the regression comparison, but the old selector treated the old regression
PASS as if it had followed the newer FAIL.

The correction is confined to the existing owner:
`tools/saipen_engine/oracle.py::regression_evidence_verdict`. It remembers the
positions of the latest FAIL and PASS and returns the existing
`NOT_A_REGRESSION_PAIR` verdict if the PASS is earlier. It reads the supplied
authoritative record order; wall time, filesystem timestamps, descriptions
and actor identity cannot override that order. The log reader already scopes
and orders the current VERIFY cycle, and both canonical gates already call
that reader. No duplicate gate or new refusal code was introduced.

Missing halves retain `NO_REGRESSION_EVIDENCE`. A fresh PASS after the latest
FAIL still goes through the existing unchanged-verifier / changed-subject
comparison. Tickets without the machine-owned declaration keep their existing
behavior. This does not claim detection of regressions after an already
terminal Work or enforcement in a host without a blocking hook.

## Unchanged regression instrument

`tools/test_t1707_regression_chronology.py` contains eight tests of the pure
selector, actual VERIFY-to-REVIEW transition and actual final closure. The
negative gate tests compare STATE, BOARD and LOG byte for byte after refusal.
Positive controls admit a fresh repair; the final-closure control actually
finishes successfully. The verifier was finalized before the implementation
changed and copied into `tools/` without changing a byte.

- Verifier SHA256:
  `68aaf62bf06ceef23f48b5bfe4d2bb95c66fdca6caab5d9922ce224808bdf143`.
- Pre-fix subject SHA256:
  `83ed9ca24cb93f2ac5ef9822f89f2cbea1be7f1bd9ed79c1c47c8810dbaa02ba`.
- Corrected subject SHA256:
  `61d4b36335f775862ffc3a82b83601387fc6c08a7705b580c8fb5b9b83fc8e9a`.
- `chronology-frozen-red-{1,2,3}.json/.txt`: three actual runs against the
  pre-fix live subject, eight tests each, the same four failures, no errors.
- `chronology-frozen-green-{1,2,3}.json/.txt`: three runs after the correction,
  eight tests each, zero failures/errors, unchanged verifier.
- `chronology-control.json`: PASS. A disposable copy ran the exact same
  command seven times: current once, restored-old and restored-current three
  times each. Only `oracle.py` changed between runs. Every restored-old run
  collected all eight tests and produced the same four named failures; every
  current/restored-current run passed. Raw outputs, subject/verifier hashes
  and command arguments are retained. Neither live file changed.

## Scope and validation

- `chronology-focused-v2.json/.txt`: 147 tests, zero failures/errors, one
  declared skip. Includes the existing regression gate, oracle, evidence/log
  classifiers and the whole-source refusal registry, canonical command
  reachability and subprocess UTF-8 contracts.
- The earlier `chronology-focused.json/.txt` is retained as a failed
  instrument invocation: two guessed module names did not exist. It is not a
  product-failure finding and does not receive a PASS claim. The corrected
  invocation names the repository's actual modules and has separate evidence.
- `chronology-lint.json/.txt`: the canonical Ruff surface `tools/ tests/`,
  exit 0. `chronology-whitespace.json/.txt`: whitespace check, exit 0.
- `index-t1707.json` and exact before/after index projections prove the new
  test is the only changed index entry. All inherited staging remains intact;
  HEAD remains `025bf596c683464788ab698248e8a3c5eb44dfec`.
- `chronology-before-family.json`: final source fingerprint
  `405e98b5e035effc3d0f79e30fa8e9ceea30e325bdc457b22462fa3541f8df70`.
- `full-family-final`: fresh whole-family run for T-1707, six isolated
  shards. Completion and a final native validator receipt are pending.
  The earlier T-1705 fresh run was cancelled before a verdict to correct this
  newly proven bug. `chronology-identities-before.json` records that
  cancellation explicitly; an interrupted family is never PASS evidence.

## Canonical boundaries

T-1707 was recorded through SAIOPS at E-14233. E-14234/E-14235 retain the
observed FAIL/PASS identities, and E-14236 records the focused results and
pending whole family. It remains an open local candidate. Its initial ticket
record does not contain `regression: required`; no supported ticket-field
updater was found, and the BOARD was not edited directly to retrofit it.
The actual unchanged-oracle evidence exists, but a formal closure must also
satisfy the machine-owned ticket declaration through a supported operation.

The active task remains T-1703 in REVIEW, at the inherited 20-ticket safety
valve. The user explicitly authorized hot-switch succession and continued
hardening; this is preserved in E-14232. That statement is not fabricated
into a signed host operator carrier. No legacy goal reset, terminal lifecycle
write, global hook installation, consumer repair, commit, tag or push is part
of this correction. Software evidence does not grant host authority or finish
the remaining SRC-205 roadmap.

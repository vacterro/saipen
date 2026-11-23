# T-1840 — truthful external proof renewal

The implemented route renews DONE external proof through the existing owned
PLAN/APPLY and immutable EX receipt machinery. It preserves the original Work,
authority, defect contract, owner, committed predecessor, Source/operator gates
and actual external carrying-commit ancestry. Declared external/native artifacts
must match; current owned argv checks must execute nonzero unskipped tests.
Dry run executes nothing; an unchanged valid repeat writes nothing. Historical
receipt bytes and DONE history are retained.

Two real host identity defects were found during acceptance. Windows executable
case spelling now requires both the same filesystem object and unchanged SHA256;
all other argv/runtime fields stay exact. The verifier fingerprint normalizes
the host path spelling. Regression/external execution also shares the existing
test-family diagnostic set, CODEX_TOOL_CALL_ID and PROMPT: both are absent from
the actual child and its identity. Semantic environment changes still require
new execution. Each defect has an unchanged targeted pre-fix FAIL/current PASS
log, including an actual child that rejects leaked diagnostics.

Truthful failed APPLY propagation exposed an independently invalid shared
fixture: STATE.last_event was 2 while its actual LOG ended at E-001. The fixture
now names 1. No failure/terminal assertion was weakened. The existing thirteen
authentication tests pass with that valid baseline.

## Current observations and limits

* Final canonical executed pair:
  `../regression/regression-execution-7ca06f9b2353489f893bcd8a60bd765c.json`.
  The same final oracle/context measures the saved pre-feature subject and
  current subject. Eighteen current tests pass; historical earlier pairs are
  retained and do not certify later oracle revisions.
* Native Ubuntu Python 3.12: seventeen passing controls and one explicit
  Windows-only skip, `native-linux-final.log`. The earlier default WSL had no
  Git; `/usr/bin/python3` was a refused symlink. Those failed instrument probes
  remain recorded and are not counted as passing product tests.
* EX-000013 binds actual SAI Accounts T-289 at carrying commit
  041f00ed1bc0b4b4841ca3edbb5912dd39461349, unchanged original defect contract,
  immutable EX-000012 predecessor and declared deployed runtime bytes.
  Three actual Windows broker/project checks pass without skips; canonical
  target-project hashes are unchanged, the temporary grant was revoked and
  the private fixture removed. Prior observations are preserved separately.
* A separate subsequent canonical renewal command returned ALREADY_APPLIED
  for EX-000013 with no writes or execution. A separate interpreter-case
  observation admitted the earlier current receipt with zero problems.
* `validate-final.json`: actual canonical core CURRENT_PASS, zero failures,
  sixteen reported warnings. No full publication acceptance follows.
* Earlier final selection reported 129 PASS and reused the exact record in
  6.765 seconds. Source then changed for the witnessed diagnostic defect;
  that older selection cannot certify the new generation. The final expanded
  seven-pattern selection, including T-1834 environment-owner controls, reports
  132 PASS in 207.578 seconds, record
  `../focused-unit/460a240d98bb8ea8-20261020T221149838659Z.json`.
  REVIEW independently reused its exact unchanged bytes in 7.89 seconds.
* Implementation-scoped pinned Ruff 0.16.0 and whitespace pass. The recorded
  full Ruff gate has 210 inherited findings; T-1841 owns their repair before
  the parent campaign's full publication acceptance. The shared fixture's
  existing unrelated lint is included in that debt.

The exact source/diff self-audit is by the executing agent, not an independent
agent or human. MCP graph/coverage tools were unavailable; exact source paths
and direct callers were inspected. No downstream application source, deployed
runtime, original immutable receipt or original Source disposition was edited.
SRC-188 R009/R010 are not silently discharged by a legacy empty-receipt gate.
Parent T-1839 and T-1829 retain their own current-generation/platform/full-family,
source, attribution, review and publication obligations.

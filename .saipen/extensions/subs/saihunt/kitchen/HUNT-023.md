# HUNT-023: bounded six-signal sweep at dc39709c (tree f3dab073)

Current identity: `dc39709c0c17a3272126c01a626ffcaa4176140b` /
`git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7`.
Role revision: `sha256:4edb04181cb07e0946afd06fbe711166fa9dcc403e56b52e9be3844f0a71b0a5`.
Raw capture: `_hunt023_installed_validate.json`.

This pass follows the T-2047 idempotence guard into the tree (HEAD did not
move; the worktree now carries `tools/saipen_engine/crew.py` and
`tools/test_t1430_crew_run_receipt.py`). It is bounded to the two canonical
gates, the focused-control records cited against THIS tree, and four cheap
censuses. It proposes no new ticket and converts no static count into a defect.

## Signal 1 -- failing tests/gates: REPRODUCED

Installed canonical gate: `CONFORMANCE_UNHEALTHY`, `CURRENT_FAIL`, 3 problems
/ 19 warnings, structural gate pass, install identity
`install-v1:fedda813…` running=persisted MATCH. The three problems are
SRC-418 unresolved for DONE T-2072, the audit-inbox route violation (the
installed pre-fix engine's view; the payload cannot be injected while the
surface is dirty), and FG-0046 naming absent T-1936.

Repo-generation validator at this tree: exit 1, `Validation FAILED: 29
problem(s), 39 warning(s)`. Classes: the same SRC-418/T-2072 receipt,
`EX-000053` closure provenance (verified against generation `d64ee12e…`, the
running engine is now `37dbbc7a…` because the T-2047 edit moved it), and 27
runtime-manifest paths outside Git. No audit-route failure and no FUTURE GATE
failure appear in this generation.

Instrument controls at this tree: five distinct cited focused records, 131
cases total (5 + 9 + 22 + 32 + 63), all PASS; the T-2047 anchored pair
`verifier:c89813b2` with subjects `d4b17838 -> b548fe15`. Verdict:
**REPRODUCED**, every class owned (T-2072, T-1449/T-2058, T-2070/T-2071).

## Signal 2 -- commits unverified in LOG: no claim

A literal census of the last 25 commit hashes against the LOG text finds 24
absent as literals. Literal absence cannot separate an unverified commit from
release evidence keyed by another identity. Verdict: **BLOCKED** pending
semantic release-ledger attribution; no commit is claimed unverified.

## Signal 3 -- stale TODO/FIXME/HACK: NOT_REPRODUCED

A bounded census over git-tracked `tools/`, `saipen/` and `extensions/` finds
exactly one marker line naming a ticket now in `## DONE`:
`tools/saipen_engine/reconcile.py` `(T-1609)` in a docstring that explains the
`restart: TODO` state vocabulary. That is protocol wording, not a stale
marker, so zero stale markers were reproduced. Verdict: **NOT_REPRODUCED**.

## Signal 4 -- silent failures: no claim

AST census over the same tracked set: 60 `except` handlers whose sole body is
`pass` (first: `audit_checks.py:1313`, `audit_parity.py:135`,
`improve.py:4320`, `producer_backends/saipal_adapter.py:2026`). Static shape
alone does not prove a lost required outcome. Verdict: **BLOCKED** pending
per-handler failure-path reproduction; no defect claimed.

## Signal 5 -- symmetry gaps on the T-2047 surface: REPRODUCED AS FIXED

The producer `crew_record_run` now compares the proposed binding
(epoch + role + source head + source tree fingerprint + role revision +
package-identity set) against journaled crew_run receipts and returns
`ALREADY_BOUND` without writing when an identical binding already exists;
two contract tests cover the exact replay and the changed-set case, and both
run green in the focused record.

Bounded asymmetry, recorded not claimed: the lower-level writer
`operations.record_crew_run` still has no guard of its own; the producer is
its only production caller (`crew.py:1587`; the CLI and `run_scenarios.py`
reach the producer, never the writer directly). Verdict: **REPRODUCED AS
FIXED** at the producer, with the residual writer-level asymmetry documented.

## Signal 6 -- dead code/orphan files: not measured this pass

No census was run. The 27 untracked runtime-manifest paths remain the known
publication-conformance debt (T-1449/T-2058), not evidence of dead code.
Verdict: **NO CLAIM**.

The role wrote only within `.saipen/extensions/subs/saihunt/`. No payload is
proposed. Core can bind this package to the crew epoch with the canonical
`saipen crew record-run saihunt --package HUNT-023` route.

## Addendum -- live replay measurement (after package record)

The same binding was exercised twice against the live epoch after this package
was recorded. The installed (pre-fix) engine wrote a second receipt for the
identical binding: E-21380 duplicates E-21379
(`crew-run-4b324212…`). The repo-generation engine, run on the same binding
and the same epoch, returned `ALREADY_BOUND` naming E-21379 with the LOG hash
unchanged. That is the TEST-13 S8 defect and the T-2047 fix measured on the
production path, not only in the prefix fixture. The duplicate receipt is
immutable evidence; the stage consumers read a set, so stage satisfaction is
unaffected.

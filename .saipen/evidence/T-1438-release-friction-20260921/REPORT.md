# T-1438 / SRC-094 — release friction investigation

Date: 2026-09-21, Europe/Tallinn. Baseline HEAD:
`d97abdc097db432bafe2316b1e3577e44cd9cc4c`, with pre-existing uncommitted
T-1437 changes. This report distinguishes bounded source fixes from complete
product/release readiness.

## Findings and result

The newest AUDAPACK credential-gate handoff described a real refusal without
a route: an exact archived receipt triggered SOURCE_CREDENTIALS_UNSAFE, but
the existing lossless quarantine operation was absent from the response.
The release preflight further flattened the refusal into prose.

Fixed in the existing owners:

- intake returns receipt identity and the exact canonical quarantine command;
- the closed remediation table extracts that same command into the validator
  receipt; help, command documentation and explicit effect classification agree;
- release preflight preserves the structured source gate and its route;
- the operation remains an EXECUTION effect, never a diagnostic bypass.

Actually executing the proposed remedy exposed a second defect: quarantining
an already-archived body left immutable closure references pointing at its
original location. The validator then reported an invalid tombstone and archive
bundle. Archive readers now accept the original closure reference together
with a verified distribution overlay, read the body from its current protected
location, and verify the digest. Repeating archive resolves the protected body.
No source body, archived metadata, coverage, tombstone or index is rewritten
to manufacture closure. The distribution record is the existing authority.

The reported alternative of retiring an already archived credential receipt
is not the repair. Quarantine controls distribution; lifecycle status and
amendments cannot remove the original archived bytes from export.

## Remaining release blockers and roadmap

The earlier repository-wide unrelated-coverage defect already has owners
T-1399/T-1405 marked DONE; the current implementation scopes Work coverage by
release relevance while retaining global credential/integrity checks.
Do not reopen it merely because the September 18 report exists.

Two Wintage handoffs arrived during this investigation. Current code confirms
the mechanism: a CURRENT_FAIL receipt without repair commands falls back to
`saipen validate`, and `_bounded_validator_output` keeps the tail. The live
six blocking findings were not independently captured here. The prior nine-item
debt snapshot in the report is explicitly not current evidence. T-1439 now owns
the finite-routing/complete-diagnostics follow-up with concrete exit criteria.

T-1437 remains the existing SAITULS multi-work/user-wait/closure owner.
T-1435 remains the FastPrompter four-blocker repair owner (M2-M14 pending).
T-1361 owns broader scenario failure classification. The Roadmap replaces its
obsolete active T-1432 instructions with these current dependencies, explicit
tests, human/agent benefits and delivery limits.

## Verification

- New focused suite: 8 tests PASS in HOME; `home-focused.log`.
- Related isolated source suite: 149 tests PASS; `credential-route-verified.log`.
  Covers source receipts, remediation registration/dispatch/docs, multi-work,
  debt, protocol registry and admission. Counts overlap the focused suite.
- Disposable flattened installation: 8 tests PASS; `credential-route-flat.log`.
  This is installation-layout acceptance, not a live host upgrade.
- Deliberate pre-fix reproduction: missing route and flattened refusal FAIL;
  `credential-route-red.log`. The archive problem also reproduced after the
  route-only correction; the final test executes quarantine and full validation.
- The real validator on a disposable project emits the quarantine command in
  its FAIL receipt and returns PASS after repair. Its HOME is materialized from
  the runtime manifest so unrelated incoming files cannot contaminate the oracle.
- Controls retain refusal for unfinished coverage, tampered bodies, arbitrary
  archive references and missing distribution records. Export excludes the
  protected body and retains its safe distribution record.
- Ruff over `tools/ tests/` and `git diff --check`: PASS.
- Final extended isolated run: 194 tests, 191 PASS and the same 3 pre-existing
  archive failures; `credential-route-final-family.log`. This is not a full
  repository test-family PASS.

The extended archive audit also exposes three PRE_EXISTING failures, reproduced
unchanged on the original HOME implementation before integration:
`test_untampered_interrupted_close_settles_idempotently`,
`test_corrupt_partial_archive_refusal_is_zero_write`, and
`test_source_body_limits_apply_before_write_and_during_recovery`, in
`test_audit_2026_08_28_all3.py`. They are not suppressed or called PASS.
See the extended family logs; initial exploratory logs also contain an
isolated-snapshot setup error (logs placed at its root) subsequently corrected.

## Full gate and delivery limits

HOME core before: 4 problems / 29 warnings, `home-core-before.log`.
HOME core after: 5 problems / 29 warnings, `home-core-after.log`.
The same two pre-existing test modules are untracked, and three incoming root
handoff documents fail root-file-set and coverage checks. The fifth finding is
the newly added untracked quarantine regression module: it must be included
when packaging/committing this slice. No validator rule was disabled.

The broad product is not certified release-ready. No remote release, consumer
project mutation, live installation refresh or weaker-model acceptance run
was performed. Existing uncommitted T-1437 work and incoming reports remain.

The ingress itself measured the stop/lease friction: SRC-094 was durably queued
while the previous stopped session's T-1437 claim remained fresh. Investigation
and reproduction proceeded in an isolated copy; canonical start succeeded
after the lease expired, preserving T-1437 as a dependency. No session identity
was copied and no claim timestamp was edited.

## Local checkpoint

T-1438 completed canonically at E-7754/E-7755; T-1437 resumed at SCOUT with
its existing partial BUILD work preserved. No Git commit or publication was
performed. The implementation and new regression remain in the working tree.

The first finish attempt exposed another friction point: its refusal selected
the later review RUN (which mentioned the broad gate's FAIL) instead of the
ticket's earlier explicit successful verification. The refusal supplied the
exact canonical verification-checkpoint command; E-7753 recorded the already
executed scoped proof and the next finish succeeded. No test was rerun or
global verdict changed. Keep this observation with closure-evidence work;
do not infer a new global PASS from local completion.

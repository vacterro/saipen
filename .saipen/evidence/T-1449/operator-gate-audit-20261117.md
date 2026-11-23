# T-1449 / `cc all` -- operator-gate audit, 17.11.2026

State: HEAD `dc39709c0`, STATE phase DONE / task none / next_action `saipen crew`.

## The 141 open tickets, by blocker head

| class | count |
| --- | --- |
| WAIT_USER_DECISION / WAIT_USER_CONFIRMATION | 31 |
| ACTIVE_DEPENDENCY / SEQUENCED_AFTER / HELD | 35 |
| BLOCKED_EXTERNAL / PUBLICATION_BLOCKED_EXTERNAL | 26 |
| MARKHUNT_TRIAGE_REQUIRED | 8 |
| SUPERSEDED / DUPLICATE_CONTINUATION | 7 |
| operator steering (PRIORITY_STEERING, OUT_OF_SCOPE, DEFERRED_BY_OPERATOR, PAUSED, AMENDMENT_ONLY) | 6 |
| INVALID OR AMBIGUOUS BLOCKER | 4 |
| PUBLICATION_STAGING_BLOCKED | 2 |
| other operator/structural (release evidence, authority gates, host capability, wrong project, permanent warnings) | 22 |

Dependency sweep: every ACTIVE_DEPENDENCY target is OPEN except T-2059
(DONE, E-21471), which clears T-2062's `needs:` hold. Both engines still
refuse its unblock:

- installed 8.1.0: `WAIT_USER_DECISION` -- classifies the blocker by
  free-prose substring, sees the tail's WAIT_USER_DECISION inside the T-2059
  history (the defect T-2077 fixed).
- repo 8.1.1 (carries the fix): `HOME_REQUIRED` home-dead home-divergent --
  a repo-run mutation stays refused while STATE names the installed home.

MARKHUNT x8: their own blocker records `phases/markhunt.md:30` -- explicit
human triage is required before TODO acceptance; the promotion lacked it.

Supersession check (T-1493, `SUPERSEDED_PENDING:T-1494`, successor DONE):
`tools/saipen_engine/supersession.py:120-231` requires (a) an ACTIVE
operator-ingress receipt whose body carries the grant capsule
`T-1493 - T-1494` (SRC-112 is `user_instruction` with `witness:
model_supplied` and no capsule), and (b) an E-### that is a successor-owned
RUN `verify -> PASS` explicitly targeted at T-1493 plus a later successor
completion. Neither exists.

## T-1449 itself

- `saipen ticket unblock T-1449` -> `VENDOR_ACCEPTANCE_BLOCKED` /
  `WAIT_USER_DECISION`, "unblocking requires verified operator authority or
  authentic proof".
- clean HEAD worktree (`git worktree add --detach dc39709c0`):
  `python tools/validate.py` FAILED 13 problems / 19 warnings -- all stale
  `.saipen` state of that commit (unresolved SRC-167, missing SRC-346, five
  detail_refs absent at HEAD, EX-000023/T-1630 provenance, five
  closure-evidence), every one cured in the live state; ruff 249 errors.
- live tree: `python tools/validate.py` FAILED 31 problems, all one class --
  "runtime manifest names a file git does not track" (the 31 untracked tools
  files of the pending 8.1.1 delivery); ruff 645 errors.
- family record `e3be896538c37e12-20261117T144445324632Z` PASS, new_red 0.
- `python tools/saipen.py ship --dry-run --json` -> `CREW_NOT_READY` (SC-2
  role/package evidence stale; SC-3/SC-4 waiting on it).
- `git rev-list --left-right --count origin/main...HEAD` -> 5 / 12.

## Installed conformance gate

Installed 8.1.0 `saipen validate` CURRENT_FAIL, 2 findings: (1) the audit
inbox routes `saipen audit ingest` for T-2016, which is BLOCKED_EXTERNAL on
SRC-386:R004; (2) FG-0046 names T-1936, absent from BOARD -- the rule defect
T-2071 fixed in 8.1.1, uninstalled. The repo generation refuses mutations
(`HOME_REQUIRED: home-dead: home-divergent`).

## Conclusion

Every remaining route needs the same operator act: install the 8.1.1
generation (EX-000053) through an authorized mechanism on a clean surface,
settle the origin/main lineage, then commit/release. Separately, native
grant capsules are needed for the pending supersessions and explicit human
triage for the MARKHUNT rows. No canonical mutation is available to the
agent: there is no active ticket to claim and every engine verb that would
start one refuses for the reasons above.

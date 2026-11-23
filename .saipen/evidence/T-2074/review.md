# T-2074 -- Core disposition of saitest/TEST-18

- package: saitest/TEST-18, package_identity sha256:945afd6abe3721a4771f1c6e1107e7fed753a20fc5fe605ab51cf9da0b9a28f6
- source at review: dc39709c0c17a3272126c01a626ffcaa4176140b / git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7
- verdict: VERIFIED-ACCEPTED (all load-bearing scenarios reproduce; two secondary observations moved and are noted)

## Independent measurements (`probe.txt`)

- S1 route: the projection still names work T-2016; with the production
  `tickets=board["tickets"]` argument, `audit_route_owns` is False and
  `route_violation(..., "saipen crew")` is None -- the dead end is gone from the
  router side, as recorded.
- S2 gates: installed 2 problems / 11 warnings; repo 29 problems / 16 warnings.
  The package recorded 3 / 19 and 29 / 39; the audit-route class and eight warnings
  disappeared in the collect window after the package was written. The asymmetry the
  package certifies (installed-only classes vs repo-only manifest and EX classes)
  survives.
- S3 idempotency: two consecutive `crew --dry-run --json` runs return key-sorted
  equal plans; STATE and LOG hashes are unchanged across the pair.
- S4 refusal: `crew record-run saitest --package TEST-99` returns STALE_PACKAGE,
  exit 1, STATE/LOG unchanged.
- S5 boundary: `board_scrub.restored_board_text` duplicates a present row (1 -> 2
  occurrences) on a synthetic board, as recorded. Two differences from the package:
  with a minimal fixture the duplicated text still parses, so "no longer parses" is
  fixture-dependent; and the production dry run from the repo generation refuses
  HOME_REQUIRED before any insert rather than NOTHING_TO_RESTORE. Both readings still
  support the package's verdict that the duplicating helper is not reachable through
  the canonical verb.

## Disposition

VERIFIED-ACCEPTED. No package patch exists to apply and no main-tree delta is made.
As with T-2073, closure cannot be told truthfully while publication is blocked:
`own_patch` asserts a patch that does not exist, `inherited_verified` demands
published release evidence, `finding_invalidated` would falsify a reproduced premise.
The ticket parks on the T-2058 publication staging authority.

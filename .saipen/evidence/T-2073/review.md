# T-2073 -- Core disposition of saihunt/HUNT-023

- package: saihunt/HUNT-023, package_identity sha256:c655ee3358bdab55623312b8e509e3db2f0e89d2710da65fb2b07266c1b40905
- source at review: dc39709c0c17a3272126c01a626ffcaa4176140b / git-delta-v1:f3dab073ebbfbd9021d22a0e63c2cbba72094bb6ff587c16e670aa98bd38e1d7
- verdict: VERIFIED-ACCEPTED (claims reproduced; one measured extent moved after the package was recorded)

## Independent measurements

1. Installed canonical gate (`scheduled-source/tools/validate.py`, output
   `installed_validate.txt`): 2 problems / 11 warnings. Classes: `source receipts --
   DONE Work T-2072 has unresolved source receipt SRC-418`; `FUTURE GATE: FG-0046 names
   slice ticket T-1936, which is not on BOARD`.
2. Repo-generation gate (`tools/validate.py`, output `repo_validate.txt`): 29 problems /
   16 warnings. Classes: SRC-418 (1), EX-000053 closure-provenance generation mismatch
   (1), and 27 `runtime manifest names a file git does not track` paths.
3. T-1430 guard family (`tools/test_t1430_crew_run_receipt.py`): Ran 5 tests, OK. The
   exact-replay test exercises ALREADY_BOUND with unchanged LOG; the changed-package
   test proves a different binding still records.
4. Guard presence: the installed generation's `saipen_engine/crew.py` contains no
   `ALREADY_BOUND` token (0 matches); the repo generation's producer carries the
   duplicate-binding guard. This is the producer-level asymmetry HUNT-023 documented,
   and it explains the historical duplicate event E-21380 written by the installed copy.

## Currency note (not a rejection)

HUNT-023 recorded the installed gate as 3 problems / 19 warnings. At review time it
reads 2 / 11: the audit-route problem and eight warnings disappeared between the two
measurements, in the window where `saipen sub collect` ingested three producer packages.
The package's claim was true when recorded; the extent moved afterwards. The two
surviving classes are exactly the ones the package names, and the repo classes match
its SRC-418 / manifest-paths / EX-000053 description.

## Disposition

The package is accepted as verified producer evidence: its load-bearing claims
(gate classes, guard asymmetry, the fixed producer path) reproduce here. No package
patch is applied and no main-tree delta is made -- the review contract forbids intake
patching, and the one patch in the batch (saipython/PY-19) belongs to T-2062, which
waits on BLOCKED T-2059.

Closure cannot be told truthfully today: `own_patch` would assert a local patch that
does not exist, `inherited_verified` demands published release evidence that
`closure.resolve_implementation_source` cannot find, and `finding_invalidated` would
falsely claim the premise was disproven. The ticket is parked BLOCKED on T-2058 (the
publication staging authority) rather than closed on a false statement.
